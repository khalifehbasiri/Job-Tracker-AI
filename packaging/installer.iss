#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{F2868D6B-FC90-40CF-AE49-73B644695C6D}
AppName=Job Tracker AI
AppVersion={#AppVersion}
AppPublisher=Job Tracker AI contributors
AppPublisherURL=https://github.com/khalifehbasiri/Job-Tracker-AI
AppSupportURL=https://github.com/khalifehbasiri/Job-Tracker-AI/issues
DefaultDirName={localappdata}\Programs\Job Tracker AI
DefaultGroupName=Job Tracker AI
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
OutputDir=..\dist\release
OutputBaseFilename=Job-Tracker-AI-Setup
LicenseFile=..\LICENSE
InfoBeforeFile=preview-notice.txt
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
AppMutex=Local\JobTrackerAI.Desktop
CloseApplications=no
RestartApplications=no
UninstallDisplayIcon={app}\Job-Tracker-AI.exe
SetupLogging=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\Job-Tracker-AI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Job Tracker AI"; Filename: "{app}\Job-Tracker-AI.exe"
Name: "{autodesktop}\Job Tracker AI"; Filename: "{app}\Job-Tracker-AI.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Job-Tracker-AI.exe"; Description: "Open Job Tracker AI"; Flags: nowait postinstall skipifsilent

; No user database, OS credentials, or user exports are installed or deleted here.
