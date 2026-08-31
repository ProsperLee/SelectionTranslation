; Inno Setup 6 — 划词翻译安装脚本
; 编译: packaging\build.ps1（推荐，自动传入版本号）
; 手动: ISCC.exe /DMyAppVersion=1.1.0 packaging\installer.iss
; 依赖: 先运行 packaging\build.ps1 生成 release\app\SelectionTranslation\

#define MyAppName "划词翻译"
#define MyAppNameEn "SelectionTranslation"
#ifndef MyAppVersion
  #define MyAppVersion "1.1.0"
#endif
#define MyAppPublisher "SelectionTranslation"
#define MyAppExeName "SelectionTranslation.exe"
#define MyAppRegName "SelectionTranslation"

; 相对本 .iss 所在目录
#define SourceApp "..\release\app\SelectionTranslation"
#define OutputDir "..\release"
#define SetupIcon "app.ico"

[Setup]
AppId={{A8F3C2E1-9B4D-4F6A-8C1E-7D2B5A0E3F91}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppComments=Windows 划词 / OCR 翻译与屏幕吸色
AppCopyright=Copyright (C) 2026 {#MyAppPublisher}
DefaultDirName={localappdata}\{#MyAppNameEn}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename={#MyAppNameEn}-Setup-{#MyAppVersion}
SetupIconFile={#SetupIcon}
UninstallDisplayIcon={app}\app.ico
UninstallDisplayName={#MyAppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=force
RestartApplications=no
UsePreviousAppDir=yes
LicenseFile=
VersionInfoVersion={#MyAppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} 安装程序
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
; 若已安装 Inno 中文语言包，可取消下行注释并把 english 改为第二语言
Name: "english"; MessagesFile: "compiler:Default.isl"
; Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式(&D)"; GroupDescription: "附加任务:"; Flags: unchecked
Name: "startup"; Description: "开机时自动启动（写入当前用户启动项）(&S)"; GroupDescription: "附加任务:"; Flags: unchecked

[Files]
Source: "{#SourceApp}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; 快捷方式显式使用独立高清 app.ico，避免依赖 EXE 内嵌图标被系统缩放发糊
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app.ico"; Comment: "划词 / OCR 翻译与屏幕吸色"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app.ico"; Comment: "划词 / OCR 翻译与屏幕吸色"; Tasks: desktopicon

[Registry]
; 与 boot.py 中 APP_REG_NAME 保持一致
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "{#MyAppRegName}"; \
    ValueData: """{app}\{#MyAppExeName}"""; \
    Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即运行 {#MyAppName}(&R)"; \
    Flags: nowait postinstall skipifsilent

[Code]
function BoolToJson(Value: Boolean): string;
begin
  if Value then
    Result := 'true'
  else
    Result := 'false';
end;

procedure WriteDefaultConfigIfMissing(const ConfigPath: string; StartOnBoot: Boolean);
var
  Lines: TArrayOfString;
begin
  if FileExists(ConfigPath) then
    Exit;

  SetArrayLength(Lines, 16);
  Lines[0] := '{';
  Lines[1] := '  "hotkey": "Ctrl+Alt+T",';
  Lines[2] := '  "ocr_hotkey": "Ctrl+Alt+O",';
  Lines[3] := '  "color_picker_hotkey": "Ctrl+Alt+I",';
  Lines[4] := '  "start_on_boot": ' + BoolToJson(StartOnBoot) + ',';
  Lines[5] := '  "selection_bubble": false,';
  Lines[6] := '  "window_pinned": false,';
  Lines[7] := '  "split_ratio": 0.5,';
  Lines[8] := '  "translation_width": 320,';
  Lines[9] := '  "translation_height": 320,';
  Lines[10] := '  "ocr_width": 640,';
  Lines[11] := '  "ocr_height": 320,';
  Lines[12] := '  "engine": "自动选择",';
  Lines[13] := '  "source_lang": "自动检测",';
  Lines[14] := '  "target_lang": "英语"';
  Lines[15] := '}';
  ForceDirectories(ExtractFilePath(ConfigPath));
  SaveStringsToUTF8File(ConfigPath, Lines, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  StartOnBoot: Boolean;
  ConfigPath: string;
begin
  if CurStep = ssPostInstall then
  begin
    StartOnBoot := WizardIsTaskSelected('startup');
    ConfigPath := ExpandConstant('{app}\settings_config.json');
    WriteDefaultConfigIfMissing(ConfigPath, StartOnBoot);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    RegDeleteValue(HKEY_CURRENT_USER,
      'Software\Microsoft\Windows\CurrentVersion\Run',
      '{#MyAppRegName}');
  end;
end;
