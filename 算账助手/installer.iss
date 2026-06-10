; 算账助手 v8 - Inno Setup 安装脚本
; 需要安装 Inno Setup 6: https://jrsoftware.org/isdl.php

#define AppName "算账助手"
#define AppVersion "8.0"
#define AppPublisher "圆滚滚"
#define AppExeName "算账助手.exe"
#define AppCopyright "Copyright (C) 2026 圆滚滚"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/logic19b/yuangungun--OS
AppSupportURL=https://github.com/logic19b/yuangungun--OS
AppCopyright={#AppCopyright}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=算账助手_v8_Setup
SetupIconFile=
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64bitMode=x64
UninstallDisplayName={#AppName}
; 支持中文
LanguageDetectionMethod=none

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标:"; Flags: unchecked

[Files]
; PyInstaller 打包后的 dist/算账助手/ 目录下所有文件
Source: "dist\算账助手\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\卸载{#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "立即启动{#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandirs; Name: "{app}"
