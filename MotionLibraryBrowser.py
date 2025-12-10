"""
Motion Library Browser for iClone 8
====================================
Enhanced version that browses the Content Manager motion folders
in addition to file dialog selection.

This provides a tree view of your motion library for easier selection.

Usage:
1. Load this script in iClone via Script > Load Python
2. Browse your motion library in the tree view
3. Double-click or select + Add to queue motions
4. Load to timeline and export with metadata

Author: Created for Gavin Bennett's GB Portfolio 2025 project
"""

import RLPy
import os
import json
from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.shiboken2 import wrapInstance

# Global references
motion_library_dialog = None
motion_library_callback = None


class MotionLibraryModel(QtCore.QAbstractItemModel):
    """Tree model for motion library folders."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.root_items = []
        self.folder_cache = {}
        self.load_root_folders()
    
    def load_root_folders(self):
        """Load root motion folders from Content Manager."""
        self.beginResetModel()
        self.root_items = []
        
        # Motion-related content types
        motion_types = [
            (RLPy.ETemplateRootFolder_Motion, "Motion"),
            (RLPy.ETemplateRootFolder_MotionPlus, "Motion Plus"),
            (RLPy.ETemplateRootFolder_Pose, "Pose"),
            (RLPy.ETemplateRootFolder_Expression, "Expression"),
            (RLPy.ETemplateRootFolder_Gesture, "Gesture"),
        ]
        
        for content_key, display_name in motion_types:
            try:
                folder_path = RLPy.RApplication.GetDefaultContentFolder(content_key)
                if folder_path:
                    self.root_items.append({
                        'name': display_name,
                        'path': folder_path,
                        'type': 'folder',
                        'content_key': content_key,
                        'children': None,  # Lazy load
                    })
            except:
                pass
        
        # Add custom content folder
        try:
            custom_folder = RLPy.RApplication.GetCustomContentFolder(RLPy.ETemplateRootFolder_Motion)
            if custom_folder:
                self.root_items.append({
                    'name': "Custom Motions",
                    'path': custom_folder,
                    'type': 'folder',
                    'content_key': None,
                    'children': None,
                })
        except:
            pass
        
        self.endResetModel()
    
    def get_children(self, folder_path):
        """Get children of a folder (lazy loading)."""
        if folder_path in self.folder_cache:
            return self.folder_cache[folder_path]
        
        children = []
        
        # Get subfolders
        try:
            subfolders = RLPy.RApplication.GetContentFoldersInFolder(folder_path)
            for subfolder in subfolders:
                folder_name = subfolder.split('/')[-1] if '/' in subfolder else subfolder
                children.append({
                    'name': folder_name,
                    'path': subfolder,
                    'type': 'folder',
                    'children': None,
                })
        except:
            pass
        
        # Get files
        try:
            files = RLPy.RApplication.GetContentFilesInFolder(folder_path)
            for file_path in files:
                if file_path.lower().endswith(('.rlmotion', '.imotion', '.imotionplus')):
                    file_name = os.path.basename(file_path)
                    children.append({
                        'name': file_name,
                        'path': file_path,
                        'type': 'file',
                    })
        except:
            pass
        
        self.folder_cache[folder_path] = children
        return children
    
    def index(self, row, column, parent=QtCore.QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()
        
        if not parent.isValid():
            # Root level
            if row < len(self.root_items):
                return self.createIndex(row, column, self.root_items[row])
        else:
            parent_item = parent.internalPointer()
            if parent_item and parent_item.get('type') == 'folder':
                children = self.get_children(parent_item['path'])
                if row < len(children):
                    return self.createIndex(row, column, children[row])
        
        return QtCore.QModelIndex()
    
    def parent(self, index):
        # Simplified - return invalid for now (flat-ish view)
        return QtCore.QModelIndex()
    
    def rowCount(self, parent=QtCore.QModelIndex()):
        if not parent.isValid():
            return len(self.root_items)
        
        parent_item = parent.internalPointer()
        if parent_item and parent_item.get('type') == 'folder':
            children = self.get_children(parent_item['path'])
            return len(children)
        
        return 0
    
    def columnCount(self, parent=QtCore.QModelIndex()):
        return 1
    
    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        
        item = index.internalPointer()
        if not item:
            return None
        
        if role == QtCore.Qt.DisplayRole:
            return item.get('name', '')
        elif role == QtCore.Qt.DecorationRole:
            if item.get('type') == 'folder':
                return QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_DirIcon)
            else:
                return QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_FileIcon)
        elif role == QtCore.Qt.UserRole:
            return item
        
        return None
    
    def hasChildren(self, parent=QtCore.QModelIndex()):
        if not parent.isValid():
            return len(self.root_items) > 0
        
        item = parent.internalPointer()
        return item and item.get('type') == 'folder'


class MotionQueueWidget(QtWidgets.QWidget):
    """Widget for the motion queue list."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.motion_files = []
        self.setup_ui()
    
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        label = QtWidgets.QLabel("Motion Queue:")
        layout.addWidget(label)
        
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        layout.addWidget(self.list_widget)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        
        self.remove_btn = QtWidgets.QPushButton("Remove")
        self.remove_btn.clicked.connect(self.remove_selected)
        btn_layout.addWidget(self.remove_btn)
        
        self.clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_all)
        btn_layout.addWidget(self.clear_btn)
        
        layout.addLayout(btn_layout)
    
    def add_motion(self, path, name=None):
        if path not in self.motion_files:
            self.motion_files.append(path)
            display_name = name or os.path.basename(path)
            self.list_widget.addItem(display_name)
    
    def remove_selected(self):
        for item in reversed(self.list_widget.selectedItems()):
            row = self.list_widget.row(item)
            self.list_widget.takeItem(row)
            if row < len(self.motion_files):
                del self.motion_files[row]
    
    def clear_all(self):
        self.motion_files = []
        self.list_widget.clear()
    
    def get_motion_files(self):
        # Rebuild list based on current order
        ordered_files = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            # Find matching file
            for path in self.motion_files:
                if os.path.basename(path) == item.text() or item.text() in path:
                    if path not in ordered_files:
                        ordered_files.append(path)
                        break
        return ordered_files


class MotionLibraryBrowser(QtWidgets.QWidget):
    """Main widget for browsing and loading motions."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.loaded_clips_info = []
        self.avatar = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Header
        header = QtWidgets.QLabel("Motion Library Browser")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)
        
        # Avatar selection
        avatar_layout = QtWidgets.QHBoxLayout()
        self.avatar_label = QtWidgets.QLabel("Avatar: None")
        avatar_layout.addWidget(self.avatar_label)
        
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_avatar)
        avatar_layout.addWidget(refresh_btn)
        layout.addLayout(avatar_layout)
        
        # Splitter for tree and queue
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        
        # Left side - Library browser
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        left_layout.addWidget(QtWidgets.QLabel("Content Library:"))
        
        self.tree_view = QtWidgets.QTreeView()
        self.tree_model = MotionLibraryModel()
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setHeaderHidden(True)
        self.tree_view.doubleClicked.connect(self.on_tree_double_click)
        left_layout.addWidget(self.tree_view)
        
        add_from_tree_btn = QtWidgets.QPushButton("Add Selected to Queue")
        add_from_tree_btn.clicked.connect(self.add_from_tree)
        left_layout.addWidget(add_from_tree_btn)
        
        # File dialog button
        add_files_btn = QtWidgets.QPushButton("Add from Files...")
        add_files_btn.clicked.connect(self.add_from_files)
        left_layout.addWidget(add_files_btn)
        
        splitter.addWidget(left_widget)
        
        # Right side - Queue
        self.queue_widget = MotionQueueWidget()
        splitter.addWidget(self.queue_widget)
        
        splitter.setSizes([300, 200])
        layout.addWidget(splitter)
        
        # Options
        options_layout = QtWidgets.QHBoxLayout()
        options_layout.addWidget(QtWidgets.QLabel("Gap frames:"))
        self.gap_spinbox = QtWidgets.QSpinBox()
        self.gap_spinbox.setRange(0, 100)
        self.gap_spinbox.setValue(0)
        options_layout.addWidget(self.gap_spinbox)
        options_layout.addStretch()
        layout.addLayout(options_layout)
        
        # Action buttons
        action_layout = QtWidgets.QHBoxLayout()
        
        load_btn = QtWidgets.QPushButton("Load to Timeline")
        load_btn.setStyleSheet("background-color: #4a90d9; color: white; font-weight: bold;")
        load_btn.clicked.connect(self.load_to_timeline)
        action_layout.addWidget(load_btn)
        
        export_btn = QtWidgets.QPushButton("Export FBX + JSON")
        export_btn.setStyleSheet("background-color: #5cb85c; color: white; font-weight: bold;")
        export_btn.clicked.connect(self.export_with_metadata)
        action_layout.addWidget(export_btn)
        
        layout.addLayout(action_layout)
        
        # Status
        self.status_label = QtWidgets.QLabel("Ready")
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)
        
        # Initial refresh
        self.refresh_avatar()
    
    def refresh_avatar(self):
        selected = RLPy.RScene.GetSelectedObjects()
        for obj in selected:
            if obj.GetType() == RLPy.EObjectType_Avatar:
                self.avatar = obj
                self.avatar_label.setText(f"Avatar: {obj.GetName()}")
                return
        
        avatars = RLPy.RScene.GetAvatars()
        if avatars:
            self.avatar = avatars[0]
            self.avatar_label.setText(f"Avatar: {avatars[0].GetName()}")
        else:
            self.avatar = None
            self.avatar_label.setText("Avatar: None")
    
    def on_tree_double_click(self, index):
        item = index.data(QtCore.Qt.UserRole)
        if item and item.get('type') == 'file':
            self.queue_widget.add_motion(item['path'], item['name'])
    
    def add_from_tree(self):
        indexes = self.tree_view.selectedIndexes()
        for index in indexes:
            item = index.data(QtCore.Qt.UserRole)
            if item and item.get('type') == 'file':
                self.queue_widget.add_motion(item['path'], item['name'])
    
    def add_from_files(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Select Motion Files",
            "",
            "Motion Files (*.rlmotion *.imotion *.fbx *.bvh);;All Files (*.*)"
        )
        for path in files:
            self.queue_widget.add_motion(path)
    
    def load_to_timeline(self):
        if not self.avatar:
            RLPy.RUi.ShowMessageBox("Motion Library", "No avatar found", RLPy.EMsgButton_Ok)
            return
        
        motion_files = self.queue_widget.get_motion_files()
        if not motion_files:
            RLPy.RUi.ShowMessageBox("Motion Library", "No motions in queue", RLPy.EMsgButton_Ok)
            return
        
        fps = RLPy.RGlobal.GetFps()
        gap_frames = self.gap_spinbox.value()
        gap_ms = int((gap_frames / fps) * 1000) if gap_frames > 0 else 0
        
        self.loaded_clips_info = []
        current_time_ms = 0
        
        self.status_label.setText("Loading motions...")
        QtWidgets.QApplication.processEvents()
        
        RLPy.RGlobal.BeginAction("Batch Load Motions")
        
        for i, motion_path in enumerate(motion_files):
            motion_name = os.path.splitext(os.path.basename(motion_path))[0]
            
            # Pre-load and load motion
            motion_length = RLPy.RTime(0)
            RLPy.RFileIO.PreLoadMotion(motion_path, self.avatar, motion_length)
            
            load_time = RLPy.RTime(current_time_ms)
            result = RLPy.RFileIO.LoadMotion(motion_path, load_time, self.avatar)
            
            if result == RLPy.RStatus.Success:
                skel = self.avatar.GetSkeletonComponent()
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
                        print(f"Loaded: {motion_name}")
        
        RLPy.RGlobal.EndAction()
        RLPy.RGlobal.ObjectModified(self.avatar, RLPy.EObjectType_Avatar)
        
        self.status_label.setText(f"Loaded {len(self.loaded_clips_info)} clips")
    
    def export_with_metadata(self):
        if not self.avatar:
            RLPy.RUi.ShowMessageBox("Motion Library", "No avatar found", RLPy.EMsgButton_Ok)
            return
        
        if not self.loaded_clips_info:
            RLPy.RUi.ShowMessageBox("Motion Library", "No clips loaded", RLPy.EMsgButton_Ok)
            return
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export FBX", "", "FBX Files (*.fbx)"
        )
        
        if not file_path:
            return
        
        if not file_path.lower().endswith('.fbx'):
            file_path += '.fbx'
        
        self.status_label.setText("Exporting...")
        QtWidgets.QApplication.processEvents()
        
        # Export FBX
        export_option = RLPy.EExportFbxOptions__None
        export_option2 = RLPy.EExportFbxOptions2__None
        export_option3 = RLPy.EExportFbxOptions3__None
        
        export_option |= RLPy.EExportFbxOptions_AutoSkinRigidMesh
        export_option |= RLPy.EExportFbxOptions_RemoveAllUnused
        export_option |= RLPy.EExportFbxOptions_ExportPbrTextureAsImageInFormatDirectory
        
        export_option2 |= RLPy.EExportFbxOptions2_RenameDuplicateBoneName
        export_option2 |= RLPy.EExportFbxOptions2_RenameDuplicateMaterialName
        
        try:
            RLPy.RFileIO.ExportFbxFile(
                self.avatar,
                file_path,
                export_option,
                export_option2,
                export_option3,
                RLPy.EExportTextureSize_Original,
                RLPy.EExportTextureFormat_Default,
                ""
            )
        except Exception as e:
            print(f"Export error: {e}")
        
        # Save JSON
        json_path = os.path.splitext(file_path)[0] + "_clips.json"
        fps = RLPy.RGlobal.GetFps()
        
        metadata = {
            "version": "1.0",
            "source": "iClone Motion Library Browser",
            "avatar_name": self.avatar.GetName(),
            "fps": fps,
            "total_frames": self.loaded_clips_info[-1]["end_frame"] if self.loaded_clips_info else 0,
            "clip_count": len(self.loaded_clips_info),
            "clips": self.loaded_clips_info
        }
        
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            print(f"JSON save error: {e}")
            self.status_label.setText("Export partial - JSON failed")
            return
        
        self.status_label.setText("Export complete!")
        RLPy.RUi.ShowMessageBox(
            "Motion Library Browser",
            f"Exported!\n\nFBX: {file_path}\nJSON: {json_path}",
            RLPy.EMsgButton_Ok
        )


class DialogEventCallback(RLPy.RDialogCallback):
    def __init__(self):
        RLPy.RDialogCallback.__init__(self)
    
    def OnDialogHide(self):
        return True


def run_script():
    global motion_library_dialog, motion_library_callback
    
    motion_library_dialog = RLPy.RUi.CreateRDialog()
    motion_library_dialog.SetWindowTitle("Motion Library Browser")
    
    dialog = wrapInstance(int(motion_library_dialog.GetWindow()), QtWidgets.QDialog)
    dialog.setMinimumWidth(600)
    dialog.setMinimumHeight(500)
    
    widget = MotionLibraryBrowser()
    dialog.layout().addWidget(widget)
    
    motion_library_callback = DialogEventCallback()
    motion_library_dialog.RegisterEventCallback(motion_library_callback)
    
    motion_library_dialog.Show()


if __name__ == "__main__" or True:
    run_script()
