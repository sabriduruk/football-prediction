; Futbol Tahmin - Inno Setup Script
; Bu dosyayi Inno Setup ile derleyerek kurulum dosyasi olusturabilirsiniz
; Inno Setup: https://jrsoftware.org/isinfo.php

#define MyAppName "Futbol Tahmin"
#define MyAppVersion "1.0"
#define MyAppPublisher "Futbol Tahmin"
#define MyAppURL "https://github.com/user/futbol-tahmin"
#define MyAppExeName "FutbolTahmin.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Installer cikti dosyasi
OutputDir=installer_output
OutputBaseFilename=FutbolTahmin_Setup
; Sıkıştırma
Compression=lzma2/ultra64
SolidCompression=yes
; Windows 10+ gerektir
MinVersion=10.0
; Yonetici yetkisi gerektirme (kullanici klasorune kurulum icin)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Modern gorunum
WizardStyle=modern
; Icon (varsa)
; SetupIconFile=icon.ico

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Ana executable ve tum dosyalar
Source: "dist\FutbolTahmin\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
