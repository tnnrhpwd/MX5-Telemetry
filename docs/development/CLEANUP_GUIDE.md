# Cleanup Guide - Removing MX5-Telemetry-LED-Slave

## ✅ What's Been Integrated

All functionality from the standalone **MX5-Telemetry-LED-Slave** project has been fully integrated into **MX5-Telemetry**:

| Original File | New Location | Status |
|--------------|--------------|--------|
| `MX5-Telemetry-LED-Slave/src/main.cpp` | `MX5-Telemetry/src_led_slave/main.cpp` | ✅ Copied |
| `MX5-Telemetry-LED-Slave/platformio.ini` | `MX5-Telemetry/platformio.ini` (led_slave env) | ✅ Integrated |
| `MX5-Telemetry-LED-Slave/README.md` | `MX5-Telemetry/docs/DUAL_ARDUINO_SETUP.md` | ✅ Enhanced |

## 🗑️ Safe to Delete

The **MX5-Telemetry-LED-Slave** folder can now be safely removed as it's redundant:

```powershell
# Option 1: Delete permanently
Remove-Item -Path "c:\Users\tanne\Documents\Github\MX5-Telemetry-LED-Slave" -Recurse -Force

# Option 2: Archive first (safer)
# Create archive
Compress-Archive -Path "c:\Users\tanne\Documents\Github\MX5-Telemetry-LED-Slave" `
                 -DestinationPath "c:\Users\tanne\Documents\Github\MX5-Telemetry-LED-Slave-Archive.zip"

# Then delete
Remove-Item -Path "c:\Users\tanne\Documents\Github\MX5-Telemetry-LED-Slave" -Recurse -Force
```

## 📦 New Unified Workflow

### Before (Two Separate Projects)

```
MX5-Telemetry/                  ← Master Arduino project
├── src/main.cpp
└── platformio.ini

MX5-Telemetry-LED-Slave/        ← Slave Arduino project (separate)
├── src/main.cpp
└── platformio.ini
```

**Issues:**
- Two projects to maintain
- Changes need to be synced manually
- Inconsistent LED states between projects
- Confusing which project to open

### After (Single Unified Project)

```
MX5-Telemetry/                  ← Single project for both
├── src/main.cpp                ← Master Arduino
├── src_led_slave/main.cpp      ← Slave Arduino
└── platformio.ini              ← Both environments
```

**Benefits:**
- ✅ Single source of truth
- ✅ Shared configuration
- ✅ Consistent LED states
- ✅ Easier to build both

## 🚀 Using the New Structure

### Build Both Environments

```bash
cd MX5-Telemetry

# Build master
platformio run -e nano_atmega328

# Build slave
platformio run -e led_slave
```

### Upload to Both Arduinos

```bash
# Upload master to COM3
platformio run -e nano_atmega328 --target upload --upload-port COM3

# Upload slave to COM4
platformio run -e led_slave --target upload --upload-port COM4
```

### Make Changes

**Master Arduino changes:**
- Edit: `src/main.cpp`
- Libraries: `lib/`
- Config: `lib/Config/config.h`

**Slave Arduino changes:**
- Edit: `src_led_slave/main.cpp`
- No libraries needed (except Adafruit NeoPixel auto-installed)

## 🔄 If You Need to Keep Old Project

If you want to keep the standalone project for any reason:

### Option 1: Rename It

```powershell
Rename-Item -Path "c:\Users\tanne\Documents\Github\MX5-Telemetry-LED-Slave" `
            -NewName "MX5-Telemetry-LED-Slave-OLD-DEPRECATED"
```

### Option 2: Add a Deprecation Notice

Create: `MX5-Telemetry-LED-Slave/DEPRECATED.md`

```markdown
# ⚠️ DEPRECATED

This standalone project has been integrated into MX5-Telemetry.

**New location:** `MX5-Telemetry/src_led_slave/`

**Please use:** [MX5-Telemetry](../MX5-Telemetry/)

This folder is kept for reference only.
```

## ✅ Verification Checklist

Before deleting the old project, verify:

- [ ] `MX5-Telemetry/src_led_slave/main.cpp` exists
- [ ] `MX5-Telemetry/platformio.ini` has `[env:led_slave]` section
- [ ] `MX5-Telemetry/docs/DUAL_ARDUINO_SETUP.md` exists
- [ ] `MX5-Telemetry/docs/BUILD_GUIDE.md` exists
- [ ] Led slave builds successfully: `platformio run -e led_slave`
- [ ] No custom changes in old project that weren't migrated

## 🔍 Check for Custom Changes

Before deleting, check if you made any custom modifications to the standalone project:

```powershell
# Compare main.cpp files
fc "c:\Users\tanne\Documents\Github\MX5-Telemetry-LED-Slave\src\main.cpp" `
   "c:\Users\tanne\Documents\Github\MX5-Telemetry\src_led_slave\main.cpp"
```

If there are differences, review them and copy any custom changes to the new location.

## 📝 Git Considerations

If your projects are tracked in Git:

### Option 1: Delete from Repository

```bash
cd MX5-Telemetry-LED-Slave
git log  # Review history if needed

# Then delete the entire folder
cd ..
rm -rf MX5-Telemetry-LED-Slave
```

### Option 2: Archive Branch

```bash
cd MX5-Telemetry-LED-Slave
git checkout -b archived-standalone
git push origin archived-standalone

# Tag for easy reference
git tag -a v1.0.0-standalone -m "Last standalone version before integration"
git push origin v1.0.0-standalone
```

## 🎯 Recommended Action

**Safest approach:**

1. **Archive** the old project:
   ```powershell
   Compress-Archive -Path "c:\Users\tanne\Documents\Github\MX5-Telemetry-LED-Slave" `
                    -DestinationPath "c:\Users\tanne\Documents\Github\Archives\MX5-LED-Slave-$(Get-Date -Format 'yyyyMMdd').zip"
   ```

2. **Verify** new structure works:
   ```bash
   cd MX5-Telemetry
   platformio run -e led_slave
   ```

3. **Delete** old project:
   ```powershell
   Remove-Item -Path "c:\Users\tanne\Documents\Github\MX5-Telemetry-LED-Slave" -Recurse -Force
   ```

4. **Update** VS Code workspace (if using multi-root):
   - Remove `MX5-Telemetry-LED-Slave` folder from workspace
   - Keep only `MX5-Telemetry` folder

## 📚 Updated Documentation

All documentation now references the unified structure:

- **Build Instructions:** [docs/BUILD_GUIDE.md](docs/BUILD_GUIDE.md)
- **Dual Arduino Setup:** [docs/DUAL_ARDUINO_SETUP.md](docs/DUAL_ARDUINO_SETUP.md)
- **Integration Summary:** [PROJECT_INTEGRATION_SUMMARY.md](PROJECT_INTEGRATION_SUMMARY.md)

## 🆘 Rollback Plan

If you need to rollback to separate projects:

1. Extract archive if created
2. Copy `src_led_slave/main.cpp` back to standalone project
3. Update standalone `platformio.ini` if needed

**However, the unified structure is recommended going forward.**

## ✨ Benefits Recap

**Why unified is better:**

- 📦 **Single project** to maintain
- 🔄 **Consistent codebase** for LED states
- 🚀 **Easier deployment** with both environments
- 📝 **Better documentation** all in one place
- 🔧 **Simpler debugging** with shared configuration
- 🎯 **Less confusion** about which project to use

---

**Ready to clean up?** Follow the steps above to safely remove the old standalone project.
