; Inno Setup script for Microlan installer
; Build input: dist\microlan\ (PyInstaller onedir output)

#define AppName "LAN голосовые звонки"
#define AppVersion "0.2.0"
#define AppPublisher "Microlan"
#define AppExeName "microlan.exe"
#define AppInternalName "microlan"
#define DistDir "..\\dist\\microlan"
#define IconPath "..\\assets\\icon.ico"

[Setup]
AppId=A3A22F7D-5C7F-43FC-AB31-716D0A32A54D
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
OutputDir=..\dist
OutputBaseFilename=microlan_setup_{#AppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

#if FileExists(IconPath)
SetupIconFile={#IconPath}
#endif

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные задачи:"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon


[Run]
Filename: "{app}\{#AppExeName}"; Description: "Запустить {#AppName}"; Flags: nowait postinstall skipifsilent
