; Скрипт сборки инсталлятора REapps в Inno Setup
#define MyAppName "REapps"
#define MyAppVersion "1.1.8"
#define MyAppPublisher "REdesign Buro"
#define MyAppURL "https://github.com/madweey/REapps"
#define MyAppExeName "REapps.exe"

[Setup]
AppId={{E6F3A056-2B19-4C5C-8F74-D728D1B3673F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableProgramGroupPage=yes
; Установка без прав администратора (в пользовательский каталог)
PrivilegesRequired=lowest
OutputDir=dist_installer
OutputBaseFilename=REapps_Setup_v{#MyAppVersion}
SetupIconFile=app_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Главный файл приложения из папки dist
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Иконка приложения
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

; Бинарники из корня проекта: кладутся прямо рядом с REapps.exe
Source: "ffmpeg.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "xray.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent