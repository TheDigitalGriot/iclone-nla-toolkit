"""
RTime API Diagnostic Script for iClone 8
Run this to discover what methods actually work
"""

import RLPy

print("=" * 50)
print("RTime API Diagnostic")
print("=" * 50)

# Get an RTime object from the API
end_time = RLPy.RGlobal.GetEndTime()
start_time = RLPy.RGlobal.GetStartTime()

print(f"\nRTime object: {end_time}")
print(f"Type: {type(end_time)}")

# List all available methods/attributes
print("\n--- Available methods on RTime ---")
methods = [m for m in dir(end_time) if not m.startswith('_')]
for m in methods:
    print(f"  {m}")

# Try various ways to get the value
print("\n--- Trying to extract value ---")

# Method 1: GetValue()
try:
    val = end_time.GetValue()
    print(f"GetValue(): {val}")
except Exception as e:
    print(f"GetValue(): FAILED - {e}")

# Method 2: value property
try:
    val = end_time.value
    print(f".value: {val}")
except Exception as e:
    print(f".value: FAILED - {e}")

# Method 3: Direct conversion
try:
    val = float(end_time)
    print(f"float(): {val}")
except Exception as e:
    print(f"float(): FAILED - {e}")

try:
    val = int(end_time)
    print(f"int(): {val}")
except Exception as e:
    print(f"int(): FAILED - {e}")

# Method 4: String representation
try:
    val = str(end_time)
    print(f"str(): {val}")
except Exception as e:
    print(f"str(): FAILED - {e}")

# Method 5: GetMs / GetFrames style methods
for method_name in ['GetMs', 'GetMilliseconds', 'GetFrame', 'GetFrames', 'GetTime', 'ToMs', 'ToFrame', 'AsFloat', 'AsInt']:
    try:
        method = getattr(end_time, method_name, None)
        if method:
            val = method()
            print(f"{method_name}(): {val}")
    except Exception as e:
        print(f"{method_name}(): FAILED - {e}")

# Check skeleton clip API too
print("\n--- Checking Skeleton Clip API ---")
avatars = RLPy.RScene.GetAvatars(RLPy.EAvatarType_All)
if avatars:
    avatar = avatars[0]
    print(f"Avatar: {avatar.GetName()}")
    skel = avatar.GetSkeletonComponent()
    clip_count = skel.GetClipCount()
    print(f"Clip count: {clip_count}")
    
    if clip_count > 0:
        clip = skel.GetClip(0)
        print(f"\nClip object: {clip}")
        print(f"Clip type: {type(clip)}")
        
        print("\n--- Available methods on Clip ---")
        clip_methods = [m for m in dir(clip) if not m.startswith('_')]
        for m in clip_methods:
            print(f"  {m}")
        
        # Try GetLength
        try:
            length = clip.GetLength()
            print(f"\nGetLength() returned: {length}")
            print(f"GetLength() type: {type(length)}")
            
            # Try all methods on the length RTime
            print("\n--- Methods on clip length RTime ---")
            for m in [m for m in dir(length) if not m.startswith('_')]:
                try:
                    attr = getattr(length, m)
                    if callable(attr):
                        result = attr()
                        print(f"  {m}(): {result}")
                    else:
                        print(f"  {m}: {attr}")
                except Exception as e:
                    print(f"  {m}: ERROR - {e}")
        except Exception as e:
            print(f"GetLength() failed: {e}")
else:
    print("No avatar in scene - add one first!")

print("\n" + "=" * 50)
print("Diagnostic complete")
print("=" * 50)
