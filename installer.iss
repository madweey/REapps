; Скрипт создания установщика Inno Setup для Ассистент RE
#define MyAppName "Ассистент RE"
#define MyAppVersion "1.0.6"
#define MyAppPublisher "RE Design Buro"
#define MyAppExeName "REapps.exe"

[Setup]
AppId={{E8B42A68-3F4A-4D78-9B1D-6F9346BE1A80}
AppName=Ассистент RE
AppVersion=1.0.3
AppPublisher=RE / DESIGN BURO
DefaultDirName={autopf}\REdesign
DefaultGroupName=REdesign
OutputDir=dist_installer
OutputBaseFilename=REdesign_Setup_v1.0.6
SetupIconFile=app_icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\REapps\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{group}\Удалить {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent