; Inno Setup script - turns dist\ShopStock into ShopStock-Setup.exe (installer with Desktop shortcut)
; 1) run build_windows.bat   2) open this file in Inno Setup   3) Build > Compile
#define AppName "ShopStock"
#define AppVersion "2.0"
[Setup]
AppId={{B6C8F6A2-5B6E-4B0B-9A1E-5E0B5B7A4D11}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\ShopStock
DefaultGroupName=ShopStock
OutputDir=installer_output
OutputBaseFilename=ShopStock-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
[Tasks]
Name: "desktopicon"; Description: "Create a Desktop shortcut"; Flags: checkedonce
[Files]
Source: "dist\ShopStock\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
[Icons]
Name: "{autodesktop}\ShopStock"; Filename: "{app}\ShopStock.exe"; Tasks: desktopicon
Name: "{group}\ShopStock"; Filename: "{app}\ShopStock.exe"
[Run]
Filename: "{app}\ShopStock.exe"; Description: "Start ShopStock now"; Flags: nowait postinstall skipifsilent
; Customer data lives in %LOCALAPPDATA%\ShopStock and is NOT removed on uninstall/upgrade.
