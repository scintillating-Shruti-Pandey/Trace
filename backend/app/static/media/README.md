# Trace Video Media Directory (`backend/app/static/media/`)

The Trace video player supports **flexible automatic video resolution** in this directory:

### Naming Options (Pick whichever is easiest for you):

1. **Option A: By Equipment Family (Easiest & Best for Class Demo)**
   You only need up to 4 video files to cover the entire demonstration:
   - `hydraulic.mp4` &rarr; Automatically plays for any hydraulic pump overhaul queries
   - `mechanical.mp4` &rarr; Automatically plays for extrusion frame, tabletop, and hinge queries
   - `rotating.mp4` &rarr; Automatically plays for motor shaft and radial runout queries
   - `electrical.mp4` &rarr; Automatically plays for optical camera and sensor fixture queries

2. **Option B: By Specific Asset ID**
   - `vid-01.mp4`, `vid-02.mp4`, `vid-03.mp4`, ... up to `vid-25.mp4`

3. **Option C: Universal Fallback (One file for everything)**
   - `sample.mp4` &rarr; Plays for any video query if no specific file is found

4. **Option D: Direct File Picker (No copying needed!)**
   - Click the **`📁 Load Video`** button in the web app UI to select any MP4 from your computer on the spot!
