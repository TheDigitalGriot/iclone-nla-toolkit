"""
Motion Batch Loader for iClone 8
================================
Loads multiple motion files onto the timeline sequentially and exports
with clip metadata for splitting in Blender.

Usage:
1. Load this script in iClone via Script > Load Python
2. Select your character in the scene
3. Drag motions from Content Manager OR click "Add Motions..."
4. Click "Load to Timeline" to add them sequentially
5. Click "Export FBX + JSON..." to export with metadata

Author: Created for Gavin Bennett's GB Portfolio 2025 project
"""

import RLPy
import os
import json
from PySide2 import QtWidgets, QtCore
from shiboken2 import wrapInstance

# Global references to prevent garbage collection
_motion_batch_dialog = None
_motion_batch_widget = None
_dialog_callback = None


class MotionBatchLoader:
    """Main controller for motion batch loading operations."""
    
    SUPPORTED_EXTENSIONS = ('.rlmotion', '.imotion', '.fbx', '.bvh', '.imotionplus')
    
    def __init__(self):
        self.motion_files = []
        self.loaded_clips_info = []
        self.avatar = None
    
    def get_selected_avatar(self):
        """Get the currently selected avatar, or first avatar in scene."""
        selected = RLPy.RScene.GetSelectedObjects()
        
        for obj in selected:
            if obj.GetType() == RLPy.EObjectType_Avatar:
                self.avatar = obj
                return obj
        
        avatars = RLPy.RScene.GetAvatars()
        if avatars:
            self.avatar = avatars[0]
            return avatars[0]
        
        return None
    
    def add_motion_files(self, file_paths):
        """Add motion files to the queue."""
        added = 0
        for path in file_paths:
            if path.lower().endswith(self.SUPPORTED_EXTENSIONS):
                if path not in self.motion_files:
                    self.motion_files.append(path)
                    added += 1
        return added
    
    def remove_motion_file(self, index):
        """Remove a motion file from the queue by index."""
        if 0 <= index < len(self.motion_files):
            del self.motion_files[index]
    
    def clear_motion_files(self):
        """Clear all motion files from the queue."""
        self.motion_files = []
        self.loaded_clips_info = []
    
    def move_motion_up(self, index):
        """Move a motion file up in the queue."""
        if index > 0:
            self.motion_files[index], self.motion_files[index - 1] = \
                self.motion_files[index - 1], self.motion_files[index]
    
    def move_motion_down(self, index):
        """Move a motion file down in the queue."""
        if index < len(self.motion_files) - 1:
            self.motion_files[index], self.motion_files[index + 1] = \
                self.motion_files[index + 1], self.motion_files[index]
    
    def load_motions_to_timeline(self, gap_frames=0):
        """Load all queued motions to the timeline sequentially."""
        avatar = self.get_selected_avatar()
        if not avatar:
            return [], "No avatar found in scene"
        
        if not self.motion_files:
            return [], "No motions in queue"
        
        fps = RLPy.RGlobal.GetFps()
        gap_ms = int((gap_frames / fps) * 1000) if gap_frames > 0 else 0
        
        self.loaded_clips_info = []
        current_time_ms = 0
        
        RLPy.RGlobal.BeginAction("Batch Load Motions")
        
        for i, motion_path in enumerate(self.motion_files):
            motion_name = os.path.splitext(os.path.basename(motion_path))[0]
            
            # Load motion at current time
            load_time = RLPy.RTime()
            load_time.SetValue(current_time_ms)
            
            result = RLPy.RFileIO.LoadMotion(motion_path, load_time, avatar)
            
            if result == RLPy.RStatus.Success:
                skel = avatar.GetSkeletonComponent()
                clip_count = skel.GetClipCount()
                
                if clip_count > 0:
                    clip = skel.GetClip(clip_count - 1)
                    if clip:
                        clip_length_ms = clip.GetLength().GetValue()
                        clip_length_frames = int((clip_length_ms / 1000.0) * fps)
                        
                        start_frame = int((current_time_ms / 1000.0) * fps)
                        end_frame = start_frame + clip_length_frames
                        
                        clip_info = {
                            "index": i,
                            "name": motion_name,
                            "source_file": motion_path,
                            "start_time_ms": current_time_ms,
                            "length_ms": clip_length_ms,
                            "start_frame": start_frame,
                            "end_frame": end_frame,
                            "length_frames": clip_length_frames,
                        }
                        self.loaded_clips_info.append(clip_info)
                        current_time_ms += int(clip_length_ms) + gap_ms
                        
                        print(f"Loaded: {motion_name} | Frames: {start_frame}-{end_frame}")
            else:
                print(f"Failed to load: {motion_path}")
        
        RLPy.RGlobal.EndAction()
        RLPy.RGlobal.ObjectModified(avatar, RLPy.EObjectType_Avatar)
        
        return self.loaded_clips_info, None
    
    def export_with_metadata(self, output_path):
        """Export FBX with a JSON sidecar containing clip metadata."""
        avatar = self.get_selected_avatar()
        if not avatar:
            return None, None, "No avatar found"
        
        if not self.loaded_clips_info:
            return None, None, "No clips loaded"
        
        if not output_path.lower().endswith('.fbx'):
            output_path += '.fbx'
        
        # Build export options for Blender
        export_option = RLPy.EExportFbxOptions__None
        export_option2 = RLPy.EExportFbxOptions2__None
        export_option3 = RLPy.EExportFbxOptions3__None
        
        export_option |= RLPy.EExportFbxOptions_AutoSkinRigidMesh
        export_option |= RLPy.EExportFbxOptions_RemoveAllUnused
        export_option |= RLPy.EExportFbxOptions_ExportPbrTextureAsImageInFormatDirectory
        
        export_option2 |= RLPy.EExportFbxOptions2_RenameDuplicateBoneName
        export_option2 |= RLPy.EExportFbxOptions2_RenameDuplicateMaterialName
        
        try:
            result = RLPy.RFileIO.ExportFbxFile(
                avatar,
                output_path,
                export_option,
                export_option2,
                export_option3,
                RLPy.EExportTextureSize_Original,
                RLPy.EExportTextureFormat_Default,
                ""
            )
        except Exception as e:
            print(f"FBX export error: {e}")
        
        # Save JSON sidecar
        json_path = os.path.splitext(output_path)[0] + "_clips.json"
        fps = RLPy.RGlobal.GetFps()
        
        metadata = {
            "version": "1.0",
            "source": "iClone Motion Batch Loader",
            "avatar_name": avatar.GetName(),
            "fps": fps,
            "total_frames": self.loaded_clips_info[-1]["end_frame"] if self.loaded_clips_info else 0,
            "clip_count": len(self.loaded_clips_info),
            "clips": self.loaded_clips_info
        }
        
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            return output_path, None, f"JSON save failed: {e}"
        
        return output_path, json_path, None


class MotionBatchUI(QtWidgets.QWidget):
    """PySide2 UI for the Motion Batch Loader."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.loader = MotionBatchLoader()
        self.setAcceptDrops(True)
        self.setup_ui()
    
    def setup_ui(self):
        """Create the UI layout."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Header
        header = QtWidgets.QLabel("Motion Batch Loader")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)
        
        # Avatar info
        self.avatar_label = QtWidgets.QLabel("Avatar: None")
        layout.addWidget(self.avatar_label)
        
        refresh_btn = QtWidgets.QPushButton("Refresh Avatar")
        refresh_btn.clicked.connect(self.refresh_avatar)
        layout.addWidget(refresh_btn)
        
        # Separator
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        layout.addWidget(line)
        
        # Motion list
        list_label = QtWidgets.QLabel("Motion Queue (drag from Content Manager or use Add):")
        layout.addWidget(list_label)
        
        self.motion_list = QtWidgets.QListWidget()
        self.motion_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.motion_list.setMinimumHeight(150)
        self.motion_list.setAcceptDrops(False)  # Parent handles drops
        layout.addWidget(self.motion_list)
        
        # List controls
        list_btn_layout = QtWidgets.QHBoxLayout()
        
        add_btn = QtWidgets.QPushButton("Add Motions...")
        add_btn.clicked.connect(self.add_motions)
        list_btn_layout.addWidget(add_btn)
        
        remove_btn = QtWidgets.QPushButton("Remove")
        remove_btn.clicked.connect(self.remove_selected)
        list_btn_layout.addWidget(remove_btn)
        
        clear_btn = QtWidgets.QPushButton("Clear All")
        clear_btn.clicked.connect(self.clear_all)
        list_btn_layout.addWidget(clear_btn)
        
        layout.addLayout(list_btn_layout)
        
        # Move buttons
        move_btn_layout = QtWidgets.QHBoxLayout()
        
        up_btn = QtWidgets.QPushButton("Move Up")
        up_btn.clicked.connect(self.move_up)
        move_btn_layout.addWidget(up_btn)
        
        down_btn = QtWidgets.QPushButton("Move Down")
        down_btn.clicked.connect(self.move_down)
        move_btn_layout.addWidget(down_btn)
        
        layout.addLayout(move_btn_layout)
        
        # Gap frames option
        gap_layout = QtWidgets.QHBoxLayout()
        gap_label = QtWidgets.QLabel("Gap between clips (frames):")
        gap_layout.addWidget(gap_label)
        
        self.gap_spinbox = QtWidgets.QSpinBox()
        self.gap_spinbox.setRange(0, 100)
        self.gap_spinbox.setValue(0)
        gap_layout.addWidget(self.gap_spinbox)
        
        layout.addLayout(gap_layout)
        
        # Separator
        line2 = QtWidgets.QFrame()
        line2.setFrameShape(QtWidgets.QFrame.HLine)
        layout.addWidget(line2)
        
        # Load to timeline button
        load_btn = QtWidgets.QPushButton("Load to Timeline")
        load_btn.setStyleSheet("background-color: #4a90d9; color: white; font-weight: bold; padding: 8px;")
        load_btn.clicked.connect(self.load_to_timeline)
        layout.addWidget(load_btn)
        
        # Status
        self.status_label = QtWidgets.QLabel("Ready")
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)
        
        # Separator
        line3 = QtWidgets.QFrame()
        line3.setFrameShape(QtWidgets.QFrame.HLine)
        layout.addWidget(line3)
        
        # Export section
        export_label = QtWidgets.QLabel("Export with Clip Metadata:")
        export_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(export_label)
        
        export_btn = QtWidgets.QPushButton("Export FBX + JSON...")
        export_btn.setStyleSheet("background-color: #5cb85c; color: white; font-weight: bold; padding: 8px;")
        export_btn.clicked.connect(self.export_with_metadata)
        layout.addWidget(export_btn)
        
        # Clips info
        self.clips_info_label = QtWidgets.QLabel("")
        layout.addWidget(self.clips_info_label)
        
        # Spacer
        layout.addStretch()
        
        # Initial refresh
        self.refresh_avatar()
    
    # Drag and drop handlers
    def dragEnterEvent(self, event):
        if event.mimeData():
            event.acceptProposedAction()
    
    def dragMoveEvent(self, event):
        event.acceptProposedAction()
    
    def dropEvent(self, event):
        mime_data = event.mimeData()
        dropped_files = []
        
        # Debug output
        print("=== Drop Event ===")
        for fmt in mime_data.formats():
            print(f"Format: {fmt}")
        
        # Try URLs first
        if mime_data.hasUrls():
            for url in mime_data.urls():
                path = url.toLocalFile()
                if path:
                    print(f"URL: {path}")
                    # Filter out invalid iClone placeholder paths
                    if "(?)NotExistPathForDrag(?)" in path:
                        print("  -> Skipped (content not downloaded)")
                        continue
                    if os.path.exists(path):
                        dropped_files.append(path)
                    else:
                        print(f"  -> File not found: {path}")
        
        # Try text
        if not dropped_files and mime_data.hasText():
            text = mime_data.text().strip()
            for line in text.split('\n'):
                line = line.strip()
                if line and os.path.exists(line):
                    dropped_files.append(line)
                    print(f"Text: {line}")
        
        # Try all formats for file paths
        if not dropped_files:
            for fmt in mime_data.formats():
                try:
                    data = bytes(mime_data.data(fmt))
                    text = data.decode('utf-8', errors='ignore')
                    # Look for paths
                    for part in text.replace('\x00', ' ').split():
                        if os.path.exists(part):
                            dropped_files.append(part)
                            print(f"Found in {fmt}: {part}")
                except:
                    pass
        
        if dropped_files:
            added = self.loader.add_motion_files(dropped_files)
            self.update_motion_list()
            self.status_label.setText(f"Added {added} motion(s)")
            event.acceptProposedAction()
        else:
            print("No valid files found in drop")
            event.ignore()
    
    def refresh_avatar(self):
        """Refresh the avatar display."""
        avatar = self.loader.get_selected_avatar()
        if avatar:
            self.avatar_label.setText(f"Avatar: {avatar.GetName()}")
        else:
            self.avatar_label.setText("Avatar: None (add a character)")
    
    def add_motions(self):
        """Open file dialog to add motion files."""
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Select Motion Files",
            "",
            "Motion Files (*.rlmotion *.imotion *.imotionplus *.fbx *.bvh);;All Files (*.*)"
        )
        
        if files:
            added = self.loader.add_motion_files(files)
            self.update_motion_list()
            self.status_label.setText(f"Added {added} motion(s)")
    
    def remove_selected(self):
        """Remove selected items from the motion list."""
        selected = self.motion_list.selectedItems()
        for item in reversed(selected):
            index = self.motion_list.row(item)
            self.loader.remove_motion_file(index)
        self.update_motion_list()
    
    def clear_all(self):
        """Clear all motions from the list."""
        self.loader.clear_motion_files()
        self.update_motion_list()
        self.status_label.setText("Cleared")
        self.clips_info_label.setText("")
    
    def move_up(self):
        """Move selected item up in the list."""
        current_row = self.motion_list.currentRow()
        if current_row > 0:
            self.loader.move_motion_up(current_row)
            self.update_motion_list()
            self.motion_list.setCurrentRow(current_row - 1)
    
    def move_down(self):
        """Move selected item down in the list."""
        current_row = self.motion_list.currentRow()
        if current_row < self.motion_list.count() - 1:
            self.loader.move_motion_down(current_row)
            self.update_motion_list()
            self.motion_list.setCurrentRow(current_row + 1)
    
    def update_motion_list(self):
        """Update the motion list widget from the loader data."""
        self.motion_list.clear()
        for path in self.loader.motion_files:
            name = os.path.basename(path)
            self.motion_list.addItem(name)
    
    def load_to_timeline(self):
        """Load all motions to the timeline."""
        gap_frames = self.gap_spinbox.value()
        
        self.status_label.setText("Loading motions...")
        QtWidgets.QApplication.processEvents()
        
        clips_info, error = self.loader.load_motions_to_timeline(gap_frames)
        
        if error:
            self.status_label.setText(error)
            RLPy.RUi.ShowMessageBox("Motion Batch Loader", error, RLPy.EMsgButton_Ok)
        elif clips_info:
            total_frames = clips_info[-1]["end_frame"]
            fps = RLPy.RGlobal.GetFps()
            duration = total_frames / fps if fps > 0 else 0
            
            self.status_label.setText(f"Loaded {len(clips_info)} clips")
            self.clips_info_label.setText(f"{len(clips_info)} clips | {total_frames} frames | {duration:.1f}s")
    
    def export_with_metadata(self):
        """Export FBX with clip metadata JSON."""
        if not self.loader.loaded_clips_info:
            RLPy.RUi.ShowMessageBox(
                "Motion Batch Loader",
                "No clips loaded. Load motions to timeline first.",
                RLPy.EMsgButton_Ok
            )
            return
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export FBX with Metadata",
            "",
            "FBX Files (*.fbx)"
        )
        
        if file_path:
            self.status_label.setText("Exporting...")
            QtWidgets.QApplication.processEvents()
            
            fbx_path, json_path, error = self.loader.export_with_metadata(file_path)
            
            if error:
                self.status_label.setText(f"Error: {error}")
            elif json_path:
                self.status_label.setText("Export complete!")
                RLPy.RUi.ShowMessageBox(
                    "Motion Batch Loader",
                    f"Exported!\n\nFBX: {fbx_path}\nJSON: {json_path}",
                    RLPy.EMsgButton_Ok
                )


class DialogEventCallback(RLPy.RDialogCallback):
    """Callback for dialog events."""
    
    def __init__(self):
        RLPy.RDialogCallback.__init__(self)
    
    def OnDialogHide(self):
        return True


def show_window():
    """Show the Motion Batch Loader window."""
    global _motion_batch_dialog, _motion_batch_widget, _dialog_callback
    
    # Close existing window if open
    if _motion_batch_dialog is not None:
        try:
            _motion_batch_dialog.Hide()
        except:
            pass
    
    # Create the dialog window
    _motion_batch_dialog = RLPy.RUi.CreateRDialog()
    _motion_batch_dialog.SetWindowTitle("Motion Batch Loader")
    
    # Wrap the dialog for PySide2
    dialog = wrapInstance(int(_motion_batch_dialog.GetWindow()), QtWidgets.QDialog)
    dialog.setMinimumWidth(350)
    dialog.setMinimumHeight(520)
    
    # Create and add our widget
    _motion_batch_widget = MotionBatchUI()
    dialog.layout().addWidget(_motion_batch_widget)
    
    # Register callback
    _dialog_callback = DialogEventCallback()
    _motion_batch_dialog.RegisterEventCallback(_dialog_callback)
    
    # Show the dialog
    _motion_batch_dialog.Show()


# Entry point - called when script is loaded
def run_script():
    show_window()


# Only run if executed directly (not on import)
if __name__ == "__main__":
    run_script()
