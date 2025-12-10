"""
NLA Clip Splitter for Blender
=============================
Imports FBX files exported from iClone's Motion Batch Loader and splits
the single animation into separate NLA tracks based on the JSON metadata.

Compatible with Blender 4.0+

Installation:
1. In Blender: Edit > Preferences > Add-ons > Install
2. Select this .py file
3. Enable "Animation: NLA Clip Splitter"

Usage:
1. File > Import > FBX with Clip Metadata (.fbx + .json)
2. Select the FBX file (JSON sidecar will be auto-detected)
3. Clips will be imported as separate NLA tracks

Author: Created for Gavin Bennett's GB Portfolio 2025 project
"""

bl_info = {
    "name": "NLA Clip Splitter",
    "author": "GB Portfolio Tools",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "File > Import, 3D View > Sidebar > NLA Splitter",
    "description": "Import FBX with clip metadata and split into NLA tracks",
    "category": "Animation",
}

import bpy
import json
import os
from bpy.props import (
    StringProperty,
    BoolProperty,
    FloatProperty,
    IntProperty,
    EnumProperty,
    CollectionProperty,
)
from bpy.types import (
    Operator,
    Panel,
    PropertyGroup,
    AddonPreferences,
)
from bpy_extras.io_utils import ImportHelper


class NLA_OT_ImportWithMetadata(Operator, ImportHelper):
    """Import FBX with clip metadata JSON and split into NLA tracks"""
    bl_idname = "import_anim.fbx_with_clips"
    bl_label = "Import FBX with Clip Metadata"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}
    
    # File browser settings
    filename_ext = ".fbx"
    filter_glob: StringProperty(
        default="*.fbx",
        options={'HIDDEN'},
    )
    
    # Import options
    create_nla_tracks: BoolProperty(
        name="Create NLA Tracks",
        description="Create separate NLA tracks for each clip",
        default=True,
    )
    
    keep_original_action: BoolProperty(
        name="Keep Original Action",
        description="Keep the original combined action in addition to split clips",
        default=False,
    )
    
    offset_to_zero: BoolProperty(
        name="Offset Clips to Frame 0",
        description="Start each clip action at frame 0 (recommended for game engines)",
        default=True,
    )
    
    use_custom_fps: BoolProperty(
        name="Override Scene FPS",
        description="Set scene FPS from clip metadata",
        default=True,
    )
    
    def execute(self, context):
        # Determine JSON path
        fbx_path = self.filepath
        json_path = os.path.splitext(fbx_path)[0] + "_clips.json"
        
        # Check if JSON exists
        if not os.path.exists(json_path):
            self.report({'WARNING'}, f"No clip metadata found at {json_path}. Importing FBX only.")
            bpy.ops.import_scene.fbx(filepath=fbx_path)
            return {'FINISHED'}
        
        # Load metadata
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read clip metadata: {e}")
            return {'CANCELLED'}
        
        # Set FPS if requested
        if self.use_custom_fps and 'fps' in metadata:
            context.scene.render.fps = int(metadata['fps'])
            context.scene.render.fps_base = 1.0
        
        # Import FBX
        bpy.ops.import_scene.fbx(filepath=fbx_path)
        
        # Find the armature that was just imported
        armature = None
        for obj in context.selected_objects:
            if obj.type == 'ARMATURE':
                armature = obj
                break
        
        if not armature:
            # Try to find by name from metadata
            if 'avatar_name' in metadata:
                armature = bpy.data.objects.get(metadata['avatar_name'])
            
            if not armature:
                # Find any armature
                for obj in bpy.data.objects:
                    if obj.type == 'ARMATURE':
                        armature = obj
                        break
        
        if not armature:
            self.report({'ERROR'}, "No armature found in imported file")
            return {'CANCELLED'}
        
        # Ensure armature is active
        context.view_layer.objects.active = armature
        
        # Get the original action
        if not armature.animation_data or not armature.animation_data.action:
            self.report({'ERROR'}, "No animation data found on armature")
            return {'CANCELLED'}
        
        original_action = armature.animation_data.action
        original_action_name = original_action.name
        
        # Split into clips
        clips = metadata.get('clips', [])
        if not clips:
            self.report({'WARNING'}, "No clips found in metadata")
            return {'FINISHED'}
        
        created_actions = []
        
        for clip in clips:
            clip_name = clip.get('name', f"Clip_{clip.get('index', 0)}")
            start_frame = clip.get('start_frame', 0)
            end_frame = clip.get('end_frame', 0)
            
            # Create new action
            new_action = bpy.data.actions.new(name=clip_name)
            created_actions.append((new_action, clip))
            
            # Copy fcurves within frame range
            for fcurve in original_action.fcurves:
                # Create new fcurve in new action
                new_fcurve = new_action.fcurves.new(
                    data_path=fcurve.data_path,
                    index=fcurve.array_index,
                    action_group=fcurve.group.name if fcurve.group else ""
                )
                
                # Copy keyframes within range
                for keyframe in fcurve.keyframe_points:
                    frame = keyframe.co.x
                    if start_frame <= frame <= end_frame:
                        # Offset to start at frame 0 if requested
                        new_frame = frame - start_frame if self.offset_to_zero else frame
                        
                        new_kf = new_fcurve.keyframe_points.insert(
                            frame=new_frame,
                            value=keyframe.co.y,
                            options={'FAST'}
                        )
                        
                        # Copy keyframe properties
                        new_kf.interpolation = keyframe.interpolation
                        new_kf.easing = keyframe.easing
                        new_kf.handle_left_type = keyframe.handle_left_type
                        new_kf.handle_right_type = keyframe.handle_right_type
                        
                        # Copy handles (offset if needed)
                        if self.offset_to_zero:
                            new_kf.handle_left = (
                                keyframe.handle_left[0] - start_frame,
                                keyframe.handle_left[1]
                            )
                            new_kf.handle_right = (
                                keyframe.handle_right[0] - start_frame,
                                keyframe.handle_right[1]
                            )
                        else:
                            new_kf.handle_left = keyframe.handle_left
                            new_kf.handle_right = keyframe.handle_right
                
                # Update fcurve
                new_fcurve.update()
            
            print(f"Created action: {clip_name} (frames {start_frame}-{end_frame})")
        
        # Create NLA tracks if requested
        if self.create_nla_tracks and created_actions:
            # Ensure animation data exists
            if not armature.animation_data:
                armature.animation_data_create()
            
            # Clear the active action first to avoid conflicts
            armature.animation_data.action = None
            
            # Create NLA tracks for each clip
            for action, clip in created_actions:
                # Create new track
                track = armature.animation_data.nla_tracks.new()
                track.name = action.name
                
                # Calculate strip start frame
                if self.offset_to_zero:
                    strip_start = 0
                else:
                    strip_start = clip.get('start_frame', 0)
                
                # Add strip to track
                try:
                    strip = track.strips.new(action.name, int(strip_start), action)
                    strip.name = action.name
                    
                    # Mute by default so they don't all play at once
                    track.mute = True
                except Exception as e:
                    print(f"Failed to create NLA strip for {action.name}: {e}")
            
            # Unmute the first track
            if armature.animation_data.nla_tracks:
                armature.animation_data.nla_tracks[0].mute = False
        
        # Handle original action
        if not self.keep_original_action:
            # Remove original action
            if original_action.users == 0:
                bpy.data.actions.remove(original_action)
            else:
                # Mark for deletion
                original_action.use_fake_user = False
        
        self.report({'INFO'}, f"Imported {len(created_actions)} clips as NLA tracks")
        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        
        layout.prop(self, "create_nla_tracks")
        layout.prop(self, "keep_original_action")
        layout.prop(self, "offset_to_zero")
        layout.prop(self, "use_custom_fps")


class NLA_OT_SplitActiveAction(Operator):
    """Split the active action into NLA tracks using clip metadata"""
    bl_idname = "nla.split_from_metadata"
    bl_label = "Split Action from Metadata"
    bl_options = {'REGISTER', 'UNDO'}
    
    json_path: StringProperty(
        name="Metadata JSON",
        description="Path to the clips JSON file",
        subtype='FILE_PATH',
    )
    
    offset_to_zero: BoolProperty(
        name="Offset Clips to Frame 0",
        description="Start each clip action at frame 0",
        default=True,
    )
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'ARMATURE' and 
                obj.animation_data and obj.animation_data.action)
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        if not os.path.exists(self.json_path):
            self.report({'ERROR'}, "Metadata file not found")
            return {'CANCELLED'}
        
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read metadata: {e}")
            return {'CANCELLED'}
        
        armature = context.active_object
        original_action = armature.animation_data.action
        
        clips = metadata.get('clips', [])
        if not clips:
            self.report({'WARNING'}, "No clips in metadata")
            return {'CANCELLED'}
        
        created_count = 0
        
        for clip in clips:
            clip_name = clip.get('name', f"Clip_{clip.get('index', 0)}")
            start_frame = clip.get('start_frame', 0)
            end_frame = clip.get('end_frame', 0)
            
            # Create new action
            new_action = bpy.data.actions.new(name=clip_name)
            
            # Copy fcurves
            for fcurve in original_action.fcurves:
                new_fcurve = new_action.fcurves.new(
                    data_path=fcurve.data_path,
                    index=fcurve.array_index,
                    action_group=fcurve.group.name if fcurve.group else ""
                )
                
                for keyframe in fcurve.keyframe_points:
                    frame = keyframe.co.x
                    if start_frame <= frame <= end_frame:
                        new_frame = frame - start_frame if self.offset_to_zero else frame
                        new_kf = new_fcurve.keyframe_points.insert(
                            frame=new_frame,
                            value=keyframe.co.y,
                            options={'FAST'}
                        )
                        new_kf.interpolation = keyframe.interpolation
                
                new_fcurve.update()
            
            # Create NLA track
            track = armature.animation_data.nla_tracks.new()
            track.name = clip_name
            
            strip_start = 0 if self.offset_to_zero else start_frame
            strip = track.strips.new(clip_name, int(strip_start), new_action)
            track.mute = True
            
            created_count += 1
        
        # Unmute first track
        if armature.animation_data.nla_tracks:
            armature.animation_data.nla_tracks[0].mute = False
        
        armature.animation_data.action = None
        
        self.report({'INFO'}, f"Created {created_count} NLA tracks")
        return {'FINISHED'}


class NLA_OT_SplitByMarkers(Operator):
    """Split the active action into NLA tracks using timeline markers"""
    bl_idname = "nla.split_by_markers"
    bl_label = "Split Action by Markers"
    bl_options = {'REGISTER', 'UNDO'}
    
    offset_to_zero: BoolProperty(
        name="Offset Clips to Frame 0",
        description="Start each clip action at frame 0",
        default=True,
    )
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'ARMATURE' and 
                obj.animation_data and obj.animation_data.action and
                len(context.scene.timeline_markers) >= 2)
    
    def execute(self, context):
        armature = context.active_object
        original_action = armature.animation_data.action
        
        # Get sorted markers
        markers = sorted(context.scene.timeline_markers, key=lambda m: m.frame)
        
        if len(markers) < 2:
            self.report({'ERROR'}, "Need at least 2 markers to define clips")
            return {'CANCELLED'}
        
        created_count = 0
        
        for i in range(len(markers) - 1):
            start_marker = markers[i]
            end_marker = markers[i + 1]
            
            clip_name = start_marker.name if start_marker.name else f"Clip_{i}"
            start_frame = start_marker.frame
            end_frame = end_marker.frame - 1  # End before next marker
            
            # Create new action
            new_action = bpy.data.actions.new(name=clip_name)
            
            # Copy fcurves
            for fcurve in original_action.fcurves:
                new_fcurve = new_action.fcurves.new(
                    data_path=fcurve.data_path,
                    index=fcurve.array_index,
                    action_group=fcurve.group.name if fcurve.group else ""
                )
                
                for keyframe in fcurve.keyframe_points:
                    frame = keyframe.co.x
                    if start_frame <= frame <= end_frame:
                        new_frame = frame - start_frame if self.offset_to_zero else frame
                        new_kf = new_fcurve.keyframe_points.insert(
                            frame=new_frame,
                            value=keyframe.co.y,
                            options={'FAST'}
                        )
                        new_kf.interpolation = keyframe.interpolation
                
                new_fcurve.update()
            
            # Create NLA track
            track = armature.animation_data.nla_tracks.new()
            track.name = clip_name
            
            strip_start = 0 if self.offset_to_zero else start_frame
            strip = track.strips.new(clip_name, int(strip_start), new_action)
            track.mute = True
            
            created_count += 1
        
        # Handle last marker to end of action
        if markers:
            last_marker = markers[-1]
            # Check if there's content after last marker
            max_frame = 0
            for fcurve in original_action.fcurves:
                for kf in fcurve.keyframe_points:
                    max_frame = max(max_frame, kf.co.x)
            
            if max_frame > last_marker.frame:
                clip_name = last_marker.name if last_marker.name else f"Clip_{len(markers)-1}"
                start_frame = last_marker.frame
                end_frame = max_frame
                
                new_action = bpy.data.actions.new(name=clip_name)
                
                for fcurve in original_action.fcurves:
                    new_fcurve = new_action.fcurves.new(
                        data_path=fcurve.data_path,
                        index=fcurve.array_index,
                        action_group=fcurve.group.name if fcurve.group else ""
                    )
                    
                    for keyframe in fcurve.keyframe_points:
                        frame = keyframe.co.x
                        if start_frame <= frame <= end_frame:
                            new_frame = frame - start_frame if self.offset_to_zero else frame
                            new_kf = new_fcurve.keyframe_points.insert(
                                frame=new_frame,
                                value=keyframe.co.y,
                                options={'FAST'}
                            )
                            new_kf.interpolation = keyframe.interpolation
                    
                    new_fcurve.update()
                
                track = armature.animation_data.nla_tracks.new()
                track.name = clip_name
                strip = track.strips.new(clip_name, 0 if self.offset_to_zero else int(start_frame), new_action)
                track.mute = True
                
                created_count += 1
        
        # Unmute first track
        if armature.animation_data.nla_tracks:
            armature.animation_data.nla_tracks[0].mute = False
        
        armature.animation_data.action = None
        
        self.report({'INFO'}, f"Created {created_count} NLA tracks from markers")
        return {'FINISHED'}


class NLA_OT_ExportActionsAsGLTF(Operator):
    """Export each NLA track action as a separate GLTF file"""
    bl_idname = "nla.export_actions_gltf"
    bl_label = "Export Actions as Separate GLTF"
    bl_options = {'REGISTER'}
    
    directory: StringProperty(
        name="Output Directory",
        subtype='DIR_PATH',
    )
    
    include_armature: BoolProperty(
        name="Include Armature",
        description="Include armature mesh in each export",
        default=False,
    )
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'ARMATURE' and 
                obj.animation_data and obj.animation_data.nla_tracks)
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        armature = context.active_object
        
        if not os.path.isdir(self.directory):
            os.makedirs(self.directory)
        
        exported_count = 0
        
        for track in armature.animation_data.nla_tracks:
            for strip in track.strips:
                if strip.action:
                    action = strip.action
                    
                    # Set as active action
                    armature.animation_data.action = action
                    
                    # Export path
                    export_path = os.path.join(self.directory, f"{action.name}.glb")
                    
                    try:
                        bpy.ops.export_scene.gltf(
                            filepath=export_path,
                            export_format='GLB',
                            export_animations=True,
                            export_animation_mode='ACTIVE_ACTIONS',
                            use_selection=True if self.include_armature else False,
                        )
                        exported_count += 1
                        print(f"Exported: {export_path}")
                    except Exception as e:
                        print(f"Failed to export {action.name}: {e}")
        
        armature.animation_data.action = None
        
        self.report({'INFO'}, f"Exported {exported_count} animation files")
        return {'FINISHED'}


class NLA_PT_SplitterPanel(Panel):
    """Panel in the 3D View sidebar for NLA Clip Splitter tools"""
    bl_label = "NLA Clip Splitter"
    bl_idname = "NLA_PT_splitter_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'NLA Splitter'
    
    def draw(self, context):
        layout = self.layout
        
        obj = context.active_object
        
        # Status
        box = layout.box()
        box.label(text="Status:", icon='INFO')
        
        if obj and obj.type == 'ARMATURE':
            box.label(text=f"Armature: {obj.name}")
            
            if obj.animation_data:
                if obj.animation_data.action:
                    box.label(text=f"Action: {obj.animation_data.action.name}")
                else:
                    box.label(text="Action: None")
                
                track_count = len(obj.animation_data.nla_tracks) if obj.animation_data.nla_tracks else 0
                box.label(text=f"NLA Tracks: {track_count}")
            else:
                box.label(text="No animation data")
        else:
            box.label(text="Select an armature")
        
        layout.separator()
        
        # Import section
        box = layout.box()
        box.label(text="Import", icon='IMPORT')
        box.operator("import_anim.fbx_with_clips", text="Import FBX + Clips")
        
        layout.separator()
        
        # Split section
        box = layout.box()
        box.label(text="Split Animation", icon='NLA')
        
        col = box.column(align=True)
        col.operator("nla.split_from_metadata", text="Split from JSON Metadata")
        col.operator("nla.split_by_markers", text="Split by Timeline Markers")
        
        layout.separator()
        
        # Export section
        box = layout.box()
        box.label(text="Export", icon='EXPORT')
        box.operator("nla.export_actions_gltf", text="Export Actions as GLTF")
        
        layout.separator()
        
        # Quick actions
        box = layout.box()
        box.label(text="Quick Actions", icon='TOOL_SETTINGS')
        
        row = box.row(align=True)
        row.operator("nla.tracks_add", text="Add Track")
        row.operator("nla.tracks_delete", text="Delete Track")


# Menu integration
def menu_func_import(self, context):
    self.layout.operator(NLA_OT_ImportWithMetadata.bl_idname, 
                         text="FBX with Clip Metadata (.fbx + .json)")


# Registration
classes = (
    NLA_OT_ImportWithMetadata,
    NLA_OT_SplitActiveAction,
    NLA_OT_SplitByMarkers,
    NLA_OT_ExportActionsAsGLTF,
    NLA_PT_SplitterPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
