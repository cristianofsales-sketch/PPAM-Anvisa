#define MyAppName "PPAM - Gerador Automático"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "PPAM"
#define MyAppExeName "PPAM.exe"

[Setup]
AppId={{A5F39A4B-742B-4A5B-B6CB-PPAM2026}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\PPAM
DefaultGroupName={#MyAppName}
OutputDir=dist-installer
OutputBaseFilename=PPAM-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "dist\PPAM\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Executar PPAM"; Flags: nowait postinstall skipifsilent
