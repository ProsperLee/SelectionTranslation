; Inno Setup 6 — 划词翻译安装脚本
; 编译: ISCC.exe packaging\installer.iss
; 依赖: 先运行 packaging\build.ps1 生成 release\app\SelectionTranslation\

#define MyAppName "划词翻译"
#define MyAppNameEn "SelectionTranslation"
#define MyAppVersion "1.0.0"
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
DefaultDirName={localappdata}\{#MyAppNameEn}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; 允许用户自由选择安装目录
AllowNoIcons=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename={#MyAppNameEn}-Setup-{#MyAppVersion}
SetupIconFile={#SetupIcon}
UninstallDisplayIcon={app}\app.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
InfoBeforeFile=
LicenseFile=

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
; If you installed the Chinese language pack, you can add:
; Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"; Flags: unchecked
Name: "startup"; Description: "开机时自动启动（写入当前用户启动项）"; GroupDescription: "附加任务:"; Flags: unchecked

[Files]
Source: "{#SourceApp}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; 快捷方式显式使用独立高清 app.ico，避免依赖 EXE 内嵌图标被系统缩放发糊
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app.ico"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app.ico"; Tasks: desktopicon

[Registry]
; 与 boot.py 中 APP_REG_NAME 保持一致
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "{#MyAppRegName}"; \
    ValueData: """{app}\{#MyAppExeName}"""; \
    Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即运行 {#MyAppName}"; \
    Flags: nowait postinstall skipifsilent

[Code]
function BoolToJson(Value: Boolean): string;
begin
  if Value then
    Result := 'true'
  else
    Result := 'false';
end;

procedure WriteStartupConfig(const ConfigPath: string; StartOnBoot: Boolean);
var
  Lines: TArrayOfString;
begin
  SetArrayLength(Lines, 7);
  Lines[0] := '{';
  Lines[1] := '  "hotkey": "Alt+Shift+Q",';
  Lines[2] := '  "ocr_hotkey": "Alt+Shift+W",';
  Lines[3] := '  "start_on_boot": ' + BoolToJson(StartOnBoot) + ',';
  Lines[4] := '  "selection_bubble": false,';
  Lines[5] := '  "window_pinned": true';
  Lines[6] := '}';
  ForceDirectories(ExtractFilePath(ConfigPath));
  // WriteBOM=False so Python json.loads does not fail
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
    // Always overwrite so settings checkbox matches installer choice
    ConfigPath := ExpandConstant('{app}\settings_config.json');
    WriteStartupConfig(ConfigPath, StartOnBoot);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  // Registry already uses uninsdeletevalue; delete Run value as a fallback
  if CurUninstallStep = usPostUninstall then
  begin
    RegDeleteValue(HKEY_CURRENT_USER,
      'Software\Microsoft\Windows\CurrentVersion\Run',
      '{#MyAppRegName}');
  end;
end;
