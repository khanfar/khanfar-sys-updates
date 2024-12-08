# Khanfar Systems OTA Update Guide

This guide explains how to manage and publish Over-The-Air (OTA) updates for Khanfar Systems applications.

## Prerequisites

1. GitHub Access:
   - GitHub account with access to the repository
   - GitHub Personal Access Token with `repo` scope
   - Repository URL: https://github.com/khanfar/khanfar-sys-updates

2. Required Files:
   - Latest source code from the development repository
   - PyInstaller for building EXE files
   - Access to the OTA update interface

## Pre-Update Checklist

Before publishing an update, verify:

1. Source Code:
   - All changes are committed and tested
   - Version numbers are updated in:
     - `version.json`
     - Main application file
     - Any version-dependent modules

2. Build Environment:
   - Clean the `dist` directory
   - Remove old `.spec` files
   - Ensure all dependencies are up to date

3. Version Consistency:
   - Check version numbers match across all files
   - Ensure the new version is higher than the current version in `version.json`
   - Follow versioning format: X.Y.Z (e.g., 1.0.2)

## Building the Update

1. Build the EXE:
   ```bash
   pyinstaller --clean --onefile --noconsole Khanfar-Sys.py
   ```

2. Verify the Build:
   - Test the EXE in a clean environment
   - Check all features work correctly
   - Verify no console window appears
   - Test update-specific functionality

## Publishing an Update

1. Access the Update Interface:
   - Go to: https://khanfar.github.io/khanfar-sys-updates/lg3_lfs.html
   - Enter your GitHub token when prompted

2. Upload Process:
   - Click "Select EXE File"
   - Choose the newly built EXE from the `dist` directory
   - Enter the new version number (e.g., "1.0.2")
   - Write a detailed changelog
   - Click "Publish Update"

3. Verify Upload:
   - Check the console log for successful upload
   - Verify all chunks were uploaded
   - Confirm the pull request was created

4. Check Repository:
   - Review the pull request
   - Verify `version.json` was updated correctly
   - Check file chunks were uploaded properly
   - Merge the pull request if everything is correct

## Version Control

1. Version Format:
   - Major.Minor.Patch (e.g., 1.0.2)
   - Increment appropriately:
     - Major: Breaking changes
     - Minor: New features
     - Patch: Bug fixes

2. Version Files to Update:
   - `version.json` in update repository
   - Main application version constant
   - Any version-dependent configuration files

## Troubleshooting

### If Upload Fails:
1. Check GitHub token validity
2. Verify internet connection
3. Try uploading in smaller chunks
4. Check GitHub repository permissions

### If Version Conflict:
1. Check current `version.json` on GitHub
2. Ensure new version is higher than existing
3. Update version numbers if needed
4. Try upload again

### Emergency Reset Procedure

If serious issues occur with an update:

1. Reset version.json:
   - Go to repository on GitHub
   - Edit version.json
   - Reset to last known good version
   - Update changelog to indicate rollback

2. Remove Problematic Files:
   - Delete problematic EXE chunks
   - Update version.json to remove file entries
   - Commit changes

3. Push Emergency Update:
   - Build last known good version
   - Upload through interface
   - Mark as critical update in changelog

## Best Practices

1. Testing:
   - Always test updates in isolated environment
   - Verify update process works end-to-end
   - Test rollback procedures
   - Check all features after update

2. Documentation:
   - Keep detailed changelog
   - Document any special update requirements
   - Note any breaking changes
   - Include upgrade instructions if needed

3. Version Management:
   - Keep backup of previous versions
   - Document dependencies for each version
   - Maintain compatibility information
   - Track minimum required versions

4. Security:
   - Keep GitHub tokens secure
   - Never share credentials
   - Review file permissions
   - Verify file hashes

## Support

For assistance with OTA updates:
- Technical Issues: Contact development team
- Access Issues: Contact repository admin
- Emergency Support: Use emergency contact list

## Regular Maintenance

1. Weekly Tasks:
   - Check update logs
   - Verify repository health
   - Clean up old file chunks
   - Update documentation if needed

2. Monthly Tasks:
   - Review update statistics
   - Check storage usage
   - Update access credentials
   - Test recovery procedures

Remember: Always prioritize stability and user experience when publishing updates. If in doubt, delay the update until all issues are resolved.
