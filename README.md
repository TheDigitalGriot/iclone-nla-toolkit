# Motion Batch Loader & NLA Clip Splitter

A two-part toolset for loading multiple motions onto the iClone timeline and splitting them into separate NLA tracks in Blender.

## Overview

This workflow solves the problem of batch-loading motions in iClone and maintaining clip separation when exporting to Blender for web 3D projects (React Three Fiber, Three.js, etc.).

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              WORKFLOW                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   iClone 8                           Blender 4.0+                       │
│   ┌──────────────────────┐          ┌──────────────────────┐           │
│   │  Motion Batch Loader │          │  NLA Clip Splitter   │           │
│   │                      │          │                      │           │
│   │  1. Add motions      │          │  4. Import FBX       │           │
│   │  2. Load to timeline │   ───►   │  5. Read JSON        │           │
│   │  3. Export FBX+JSON  │          │  6. Split to NLA     │           │
│   │                      │          │  7. Export GLB/GLTF  │           │
│   └──────────────────────┘          └──────────────────────┘           │
│                                                                          │
│   Outputs:                           Outputs:                           │
│   • character.fbx                    • Separate NLA tracks              │
│   • character_clips.json             • Individual action files          │
│                                      • Web-ready GLB exports            │
└─────────────────────────────────────────────────────────────────────────┘
```

## Part 1: iClone Motion Batch Loader

### Installation

1. Copy `MotionBatchLoader.py` to your iClone scripts folder:
   - Windows: `C:\Program Files\Reallusion\iClone 8\Bin64\OpenPlugin\`
   - Or any folder you use for iClone scripts

2. In iClone: **Script > Load Python** and select `MotionBatchLoader.py`

### Usage

1. **Add a character** to your iClone scene

2. **Open the Motion Batch Loader** (it should appear automatically when the script loads)

3. **Click "Refresh Avatar"** to detect your character

4. **Click "Add Motions..."** and select multiple motion files:
   - Supported formats: `.rlmotion`, `.imotion`, `.fbx`, `.bvh`
   - You can select from ActorCore, Mixamo, or your own motion library

5. **Reorder motions** using the Move Up/Down buttons (the order determines timeline placement)

6. **Set gap frames** (optional) - adds frames between clips for transitions

7. **Click "Load to Timeline"** - all motions will be loaded sequentially

8. **Click "Export FBX + JSON..."** to export:
   - `yourfile.fbx` - The character with all animations baked
   - `yourfile_clips.json` - Metadata with frame ranges for each clip

### JSON Metadata Format

```json
{
  "version": "1.0",
  "source": "iClone Motion Batch Loader",
  "avatar_name": "CC4_Avatar",
  "fps": 60,
  "total_frames": 450,
  "clip_count": 3,
  "clips": [
    {
      "index": 0,
      "name": "Idle",
      "source_file": "C:/Motions/Idle.rlmotion",
      "start_time_ms": 0,
      "length_ms": 3000,
      "start_frame": 0,
      "end_frame": 180,
      "length_frames": 180
    },
    {
      "index": 1,
      "name": "Walk",
      "source_file": "C:/Motions/Walk.rlmotion",
      "start_time_ms": 3000,
      "length_ms": 2000,
      "start_frame": 180,
      "end_frame": 300,
      "length_frames": 120
    }
  ]
}
```

---

## Part 2: Blender NLA Clip Splitter

### Installation

1. In Blender: **Edit > Preferences > Add-ons**
2. Click **Install...**
3. Select `nla_clip_splitter.py`
4. Enable **"Animation: NLA Clip Splitter"**

### Usage

#### Method 1: Import with Auto-Split (Recommended)

1. **File > Import > FBX with Clip Metadata (.fbx + .json)**
2. Select your `.fbx` file (the addon auto-detects the `_clips.json` sidecar)
3. Configure options:
   - **Create NLA Tracks**: Split into separate NLA tracks (default: on)
   - **Keep Original Action**: Preserve the combined animation (default: off)
   - **Offset Clips to Frame 0**: Each clip starts at frame 0 (default: on)
   - **Override Scene FPS**: Match iClone's FPS setting (default: on)

4. Click **Import**

#### Method 2: Split Existing Action

If you've already imported an FBX without the addon:

1. Select the armature with the animation
2. Open the sidebar: **View > Sidebar** (or press `N`)
3. Go to the **NLA Splitter** tab
4. Click **"Split from JSON Metadata"**
5. Select your `_clips.json` file

#### Method 3: Split by Timeline Markers

If you don't have JSON metadata:

1. Add timeline markers at clip boundaries (press `M` in the timeline)
2. Name each marker with the clip name
3. Select the armature
4. In the NLA Splitter panel, click **"Split by Timeline Markers"**

### Exporting for Web

After splitting into NLA tracks, you can export for React Three Fiber:

1. In the NLA Splitter panel, click **"Export Actions as GLTF"**
2. Choose an output directory
3. Each action will be exported as a separate `.glb` file

Or use the standard GLTF export with all animations:

1. **File > Export > glTF 2.0 (.glb/.gltf)**
2. Under Animation:
   - Enable **Export Animations**
   - Set **Animation Mode** to "NLA Tracks" or "Actions"
3. Export

---

## React Three Fiber Integration

### Loading Multiple Animations

```jsx
import { useGLTF, useAnimations } from '@react-three/drei'

function Avatar() {
  const { scene, animations } = useGLTF('/avatar.glb')
  const { ref, actions, names } = useAnimations(animations)
  
  // Actions are named after your clips: "Idle", "Walk", "Run", etc.
  useEffect(() => {
    // Play idle by default
    actions.Idle?.reset().fadeIn(0.5).play()
    
    return () => actions.Idle?.fadeOut(0.5)
  }, [])
  
  // Switch animations based on state
  const playAnimation = (name) => {
    // Fade out all current
    Object.values(actions).forEach(action => action.fadeOut(0.3))
    // Play new
    actions[name]?.reset().fadeIn(0.3).play()
  }
  
  return <primitive ref={ref} object={scene} />
}
```

### Scroll-Triggered Animations (GSAP ScrollTrigger)

```jsx
import { useGLTF, useAnimations } from '@react-three/drei'
import { useEffect } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(ScrollTrigger)

function ScrollAvatar() {
  const { scene, animations } = useGLTF('/avatar.glb')
  const { ref, actions, mixer } = useAnimations(animations)
  
  useEffect(() => {
    // Map scroll progress to animation clips
    const animationSequence = ['Idle', 'Wave', 'Walk', 'Sit']
    
    ScrollTrigger.create({
      trigger: '#scroll-container',
      start: 'top top',
      end: 'bottom bottom',
      scrub: true,
      onUpdate: (self) => {
        const progress = self.progress
        const clipIndex = Math.floor(progress * animationSequence.length)
        const clipName = animationSequence[Math.min(clipIndex, animationSequence.length - 1)]
        
        // Crossfade to new clip
        Object.entries(actions).forEach(([name, action]) => {
          if (name === clipName) {
            action.reset().fadeIn(0.3).play()
          } else {
            action.fadeOut(0.3)
          }
        })
      }
    })
  }, [actions])
  
  return <primitive ref={ref} object={scene} />
}
```

---

## Troubleshooting

### iClone Issues

**"No avatar found"**
- Make sure you have a character in the scene
- Click "Refresh Avatar" to re-detect

**Motions not loading**
- Check the console (View > Console Log) for error messages
- Ensure motion files are compatible with your character type
- Try loading the motion manually first to verify it works

**Export fails**
- Ensure you have write permissions to the export directory
- Try exporting to a simple path (e.g., `C:/Exports/`)

### Blender Issues

**JSON not found**
- The JSON file must be named `yourfile_clips.json` (same base name as FBX)
- Keep both files in the same directory

**No animation data after import**
- Make sure "Import Animation" is enabled in FBX import settings
- Check that the armature has animation data in the Dope Sheet

**NLA tracks not showing**
- Open the NLA Editor (Shift+F12 or Editor Type dropdown)
- Ensure the armature is selected
- Check that tracks aren't all muted

**Actions not exporting to GLTF**
- In GLTF export, set Animation Mode to "NLA Tracks" or "Actions"
- Ensure actions have a fake user or are in use

---

## File Structure

```
motion_batch_loader/
├── MotionBatchLoader.py     # iClone plugin
├── nla_clip_splitter.py     # Blender addon
└── README.md                # This file
```

---

## Version History

### v1.0.0
- Initial release
- iClone Motion Batch Loader with UI
- Blender NLA Clip Splitter addon
- JSON metadata format
- GLTF batch export

---

## Credits

Created for **GB Portfolio 2025** - A React Three Fiber portfolio project featuring scroll-driven 3D avatar animations.

## License

MIT License - Feel free to use, modify, and distribute.
