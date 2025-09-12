; WebCorder Secure Inno Setup Script
; Single executable installer - NO source code exposure

[Setup]
; === APPLICATION INFO ===
AppName=WebCorder
AppVersion=1.0.0
AppPublisher=Plexlevi
AppPublisherURL=https://github.com/plexlevi/webcorder
AppSupportURL=https://github.com/plexlevi/webcorder
AppUpdatesURL=https://github.com/plexlevi/webcorder

; === INSTALLATION FOLDERS ===
DefaultDirName={autopf}\WebCorder
DefaultGroupName=WebCorder
DisableProgramGroupPage=yes

; === INSTALLER SETTINGS ===
AllowNoIcons=yes
OutputDir=output
OutputBaseFilename=WebCorder-Setup-v{#SetupSetting("AppVersion")}
SetupIconFile=..\resources\icon.ico
UninstallDisplayIcon={app}\WebCorder.exe

; === COMPRESSION & SECURITY ===
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMADictionarySize=1048576

; === UI SETTINGS ===
WizardStyle=modern
DisableWelcomePage=no
WizardImageFile=compiler:WizModernImage-IS.bmp
WizardSmallImageFile=compiler:WizModernSmallImage-IS.bmp

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; === MAIN EXECUTABLE (SINGLE FILE WITH ALL SOURCE CODE) ===
; This is the ONLY file that contains all Python code - users cannot access source!
Source: "..\dist\WebCorder.exe"; DestDir: "{app}"; Flags: ignoreversion

; === RESOURCES ===
; Only include necessary resources, NO Python source files
Source: "..\resources\icon.ico"; DestDir: "{app}\resources"; Flags: ignoreversion
Source: "..\resources\logo.png"; DestDir: "{app}\resources"; Flags: ignoreversion

; === BINARY DEPENDENCIES ===
Source: "..\resources\bin\win\ffmpeg.exe"; DestDir: "{app}\resources\bin\win"; Flags: ignoreversion

; === CONFIG TEMPLATE ===
; Only include template, not actual config with tokens
Source: "..\config\webcorder_data.json"; DestDir: "{app}\config"; Flags: ignoreversion onlyifdoesntexist

[Registry]
; Register file associations if needed
Root: HKCR; Subkey: ".webcorder"; ValueType: string; ValueName: ""; ValueData: "WebCorderFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "WebCorderFile"; ValueType: string; ValueName: ""; ValueData: "WebCorder Project"; Flags: uninsdeletekey
Root: HKCR; Subkey: "WebCorderFile\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\WebCorder.exe,0"
Root: HKCR; Subkey: "WebCorderFile\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\WebCorder.exe"" ""%1"""

[Icons]
; === START MENU ICONS ===
Name: "{group}\WebCorder"; Filename: "{app}\WebCorder.exe"; IconFilename: "{app}\resources\icon.ico"
Name: "{group}\{cm:UninstallProgram,WebCorder}"; Filename: "{uninstallexe}"

; === DESKTOP ICON ===
Name: "{autodesktop}\WebCorder"; Filename: "{app}\WebCorder.exe"; IconFilename: "{app}\resources\icon.ico"; Tasks: desktopicon

; === QUICK LAUNCH ICON ===
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\WebCorder"; Filename: "{app}\WebCorder.exe"; IconFilename: "{app}\resources\icon.ico"; Tasks: quicklaunchicon

[Run]
; Run after installation
Filename: "{app}\WebCorder.exe"; Description: "{cm:LaunchProgram,WebCorder}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up user data on uninstall (optional)
Type: filesandordirs; Name: "{app}\config"
Type: filesandordirs; Name: "{app}\logs"

[Code]
// Custom installer code

procedure InitializeWizard;
begin
  // Custom initialization if needed
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  
  // Custom validation before proceeding
  if CurPageID = wpSelectDir then
  begin
    if Length(WizardDirValue) > 100 then
    begin
      MsgBox('Installation path is too long. Please choose a shorter path.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Post-installation tasks
    // Create initial config if needed
  end;
end;

[Messages]
; Custom messages
WelcomeLabel2=This will install WebCorder on your computer.%n%nWebCorder is a powerful stream recording application with automatic update capabilities.%n%nClick Next to continue.
ClickNext=Click Next to continue, or Cancel to exit Setup.
BeveledLabel=WebCorder - Secure Installation
