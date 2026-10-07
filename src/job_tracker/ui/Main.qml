import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: root
    width: 1360; height: 900
    minimumWidth: 1080; minimumHeight: 720
    visible: true
    title: "Job Tracker AI"
    color: "#f4f6f1"
    font.family: "Segoe UI"
    font.pixelSize: 14
    property int page: 0
    property var selectedApp: ({})
    property var filteredApps: backend.applications.filter(function(app) {
        var text = filter.text.toLowerCase()
        return (app.company + " " + app.role).toLowerCase().indexOf(text) >= 0 &&
            (stageFilter.currentIndex === 0 || app.stage === stageFilter.currentText)
    })
    property var search: backend.searches.filter(function(s) { return s.id === backend.selectedSearch })[0] || ({name: "Job search"})
    function countStage(stage) { return backend.applications.filter(function(a) { return a.stage === stage && a.outcome === "Active" }).length }
    function openApplication(app) {
        selectedApp = app || ({})
        company.text = app ? app.company : ""
        role.text = app ? app.role : ""
        applied.text = app ? app.applied_on : ""
        requisition.text = app ? app.requisition_id : ""
        notes.text = app ? app.notes : ""
        stage.currentIndex = app ? stage.model.indexOf(app.stage) : 0
        outcome.currentIndex = app ? outcome.model.indexOf(app.outcome) : 0
        if (app) backend.showEvents(app.id)
        applicationDialog.open()
    }
    onClosing: function(close) {
        if (backend.trayAvailable) { close.accepted = false; root.hide() }
    }
    Connections {
        target: backend
        function onImportReady() { importDialog.open() }
        function onScanReady() { scanDialog.open() }
    }
    RowLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.preferredWidth: 224; Layout.minimumWidth: 224; Layout.maximumWidth: 224; Layout.fillHeight: true
            color: "#163e36"
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 22; spacing: 12
                PlainLabel { text: "JOB TRACKER"; color: "#ffffff"; font.bold: true; font.pixelSize: 19; Layout.topMargin: 12 }
                PlainLabel { text: "A little clarity for your next move."; color: "#aac0b7"; font.pixelSize: 11; Layout.bottomMargin: 28 }
                Repeater {
                    model: ["Overview", "Applications", "Review inbox", "Email history", "Settings"]
                    delegate: ActionButton {
                        required property string modelData
                        required property int index
                        text: modelData; Layout.fillWidth: true; implicitHeight: 46
                        onClicked: root.page = index
                        background: Rectangle { color: root.page === index ? "#2c5a4e" : "transparent"; radius: 9 }
                        contentItem: PlainLabel { text: parent.text; color: root.page === index ? "white" : "#bed1c7"; verticalAlignment: Text.AlignVCenter; leftPadding: 12 }
                    }
                }
                Item { Layout.fillHeight: true }
                PlainLabel { text: "LOCAL FIRST"; color: "#aec9ba"; font.pixelSize: 10; font.letterSpacing: 2 }
                PlainLabel { text: "Your searches. Your records.\nYour API key."; color: "#d5e4db"; lineHeight: 1.4; font.pixelSize: 12 }
                Rectangle { Layout.fillWidth: true; height: 1; color: "#365d4e"; Layout.topMargin: 15 }
                PlainLabel { text: "v0.1.0  ·  Open source"; color: "#91b29f"; font.pixelSize: 11 }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            Layout.margins: 30; spacing: 20
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 6
                    PlainLabel { text: "YOUR NEXT CHAPTER"; color: "#788479"; font.pixelSize: 10; font.letterSpacing: 2 }
                    PlainLabel { text: ["Search overview", "Your applications", "Review inbox", "Import email history", "Make it yours"][root.page]; font.pixelSize: 30; font.weight: Font.DemiBold; color: "#20362e" }
                }
                Item { Layout.fillWidth: true }
                ComboBox {
                    id: searchSelector
                    Layout.preferredWidth: 230
                    model: backend.searches; textRole: "name"; valueRole: "id"
                    enabled: !backend.busy
                    currentIndex: backend.searches.findIndex(function(s) { return s.id === backend.selectedSearch })
                    onActivated: backend.selectSearch(currentValue)
                }
                ActionButton { text: "+ New search"; enabled: !backend.busy; onClicked: searchDialog.open() }
            }
            Rectangle {
                objectName: "statusBanner"
                Layout.fillWidth: true; implicitHeight: statusRow.implicitHeight + 24
                color: "#e6ede4"; radius: 10
                RowLayout {
                    id: statusRow
                    anchors.fill: parent; anchors.margins: 12
                    BusyIndicator { running: backend.busy; visible: running; implicitWidth: 22; implicitHeight: 22 }
                    PlainLabel { id: statusText; objectName: "statusText"; text: backend.message; color: "#3b594c"; wrapMode: Text.WordWrap; Layout.fillWidth: true; Layout.alignment: Qt.AlignVCenter; font.pixelSize: 12 }
                    ActionButton { objectName: "pauseScanButton"; visible: backend.scanActive; Layout.alignment: Qt.AlignVCenter; text: "Pause scan"; onClicked: backend.pauseScan() }
                }
            }
            StackLayout {
                currentIndex: root.page
                Layout.fillWidth: true; Layout.fillHeight: true
                // Overview
                ScrollView {
                    id: overviewScroll
                    contentWidth: availableWidth
                    clip: true
                    ColumnLayout {
                        width: overviewScroll.availableWidth; spacing: 20
                        RowLayout {
                            Layout.fillWidth: true
                            PlainLabel { text: root.search.name + (root.search.archived ? " · archived" : ""); color: "#46584b"; font.pixelSize: 17 }
                            Item { Layout.fillWidth: true }
                            ActionButton { text: "+ Add application"; enabled: !backend.busy; onClicked: root.openApplication(null) }
                        }
                        RowLayout {
                            Layout.fillWidth: true; spacing: 14; uniformCellSizes: true
                            Stat { label: "APPLICATIONS"; value: backend.applications.length.toString(); Layout.fillWidth: true }
                            Stat { label: "ACTIVE"; value: backend.applications.filter(function(a) { return a.outcome === "Active" }).length.toString(); Layout.fillWidth: true }
                            Stat { label: "INTERVIEWS"; value: root.countStage("Interview").toString(); Layout.fillWidth: true; accent: "#a76c2e" }
                            Stat { label: "NEEDS REVIEW"; value: backend.reviews.length.toString(); Layout.fillWidth: true; accent: "#96744d" }
                        }
                        RowLayout {
                            Layout.fillWidth: true; spacing: 20; uniformCellSizes: true
                            Card {
                                Layout.fillWidth: true; Layout.preferredHeight: 245
                                ColumnLayout {
                                    anchors.fill: parent; spacing: 16
                                    PlainLabel { text: "Where things stand"; font.bold: true; font.pixelSize: 17; color: "#263e32" }
                                    Repeater {
                                        model: ["Applied", "Assessment", "Interview", "Offer"]
                                        delegate: RowLayout {
                                            required property string modelData
                                            Layout.fillWidth: true
                                            PlainLabel { text: modelData; Layout.preferredWidth: 100; color: "#697769" }
                                            Rectangle {
                                                Layout.fillWidth: true; height: 9; radius: 4; color: "#edf1e9"
                                                Rectangle { width: parent.width * root.countStage(modelData) / Math.max(1, backend.applications.length); height: parent.height; radius: 4; color: "#438574" }
                                            }
                                            PlainLabel { text: root.countStage(modelData); Layout.preferredWidth: 25; horizontalAlignment: Text.AlignRight; color: "#46634f" }
                                        }
                                    }
                                    Item { Layout.fillHeight: true }
                                }
                            }
                            Card {
                                Layout.fillWidth: true; Layout.preferredHeight: 245
                                ColumnLayout {
                                    anchors.fill: parent
                                    PlainLabel { text: "Coming up"; font.bold: true; font.pixelSize: 17; color: "#263e32" }
                                    PlainLabel { visible: backend.tasks.filter(function(t) { return !t.completed }).length === 0; text: "No upcoming tasks yet.\nEmail invitations and deadlines appear here."; wrapMode: Text.WordWrap; color: "#849082"; Layout.fillWidth: true; Layout.topMargin: 30 }
                                    Repeater {
                                        model: backend.tasks.filter(function(t) { return !t.completed }).slice(0, 3)
                                        delegate: CheckBox {
                                            required property var modelData
                                            text: modelData.title + " · " + modelData.company + "\n" + modelData.due_at.slice(0, 16) + " UTC"
                                            enabled: !backend.busy
                                            onClicked: backend.completeTask(modelData.id, true)
                                        }
                                    }
                                    Item { Layout.fillHeight: true }
                                }
                            }
                        }
                        Card {
                            Layout.fillWidth: true
                            ColumnLayout {
                                anchors.fill: parent
                                RowLayout {
                                    Layout.fillWidth: true
                                    PlainLabel { text: "Recent applications"; font.bold: true; font.pixelSize: 17; color: "#263e32" }
                                    Item { Layout.fillWidth: true }
                                    ActionButton { text: "View all →"; flat: true; onClicked: root.page = 1 }
                                }
                                PlainLabel { visible: backend.applications.length === 0; text: "Start with a manual application, import your Excel tracker, or connect an email account."; wrapMode: Text.WordWrap; color: "#849082"; Layout.fillWidth: true; Layout.margins: 20 }
                                Repeater {
                                    model: backend.applications.slice(0, 5)
                                    delegate: ItemDelegate {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        text: modelData.company + "  /  " + modelData.role + "     ·     " + modelData.stage + " · " + modelData.outcome
                                        onClicked: root.openApplication(modelData)
                                    }
                                }
                            }
                        }
                    }
                }
                // Applications
                ColumnLayout {
                    spacing: 16
                    RowLayout {
                        Layout.fillWidth: true
                        Field { id: filter; placeholderText: "Search company or role…"; Layout.fillWidth: true }
                        ComboBox { id: stageFilter; model: ["All stages", "Applied", "Assessment", "Interview", "Offer"] }
                        ActionButton { text: "Import Excel"; enabled: !backend.busy; onClicked: backend.previewExcel() }
                        ActionButton { text: "Export Excel"; enabled: !backend.busy; onClicked: backend.exportExcel() }
                        ActionButton { text: "+ Add"; enabled: !backend.busy; onClicked: root.openApplication(null) }
                    }
                    Card {
                        Layout.fillWidth: true; Layout.fillHeight: true
                        ColumnLayout {
                            anchors.fill: parent
                            RowLayout {
                                Layout.fillWidth: true
                                PlainLabel { text: "COMPANY / ROLE"; Layout.fillWidth: true; color: "#7d897b"; font.pixelSize: 11 }
                                PlainLabel { text: "STAGE"; Layout.preferredWidth: 110; color: "#7d897b"; font.pixelSize: 11 }
                                PlainLabel { text: "OUTCOME"; Layout.preferredWidth: 110; color: "#7d897b"; font.pixelSize: 11 }
                                PlainLabel { text: "APPLIED"; Layout.preferredWidth: 100; color: "#7d897b"; font.pixelSize: 11 }
                                Item { Layout.preferredWidth: 65 }
                            }
                            ListView {
                                Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 3
                                model: root.filteredApps
                                delegate: ItemDelegate {
                                    required property var modelData
                                    width: ListView.view.width; height: 76
                                    onClicked: root.openApplication(modelData)
                                    contentItem: RowLayout {
                                        ColumnLayout {
                                            Layout.fillWidth: true; spacing: 3
                                            PlainLabel { text: modelData.company; font.bold: true; color: "#2b4434"; Layout.fillWidth: true; elide: Text.ElideRight }
                                            PlainLabel { text: modelData.role; color: "#7d897b"; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight }
                                        }
                                        PlainLabel { text: modelData.stage; Layout.preferredWidth: 110; color: "#216e62" }
                                        PlainLabel { text: modelData.outcome; Layout.preferredWidth: 110; color: modelData.outcome === "Rejected" ? "#b36e62" : "#697d65" }
                                        PlainLabel { text: modelData.applied_on || "Unknown"; Layout.preferredWidth: 100; color: "#8c958a"; font.pixelSize: 12 }
                                        PlainLabel { text: "Open →"; Layout.preferredWidth: 65; color: "#6b8473" }
                                    }
                                }
                                PlainLabel { anchors.centerIn: parent; visible: root.filteredApps.length === 0; text: "No applications to show."; color: "#8a9788" }
                            }
                        }
                    }
                }
                // Review inbox
                ScrollView {
                    id: reviewScroll
                    contentWidth: availableWidth
                    clip: true
                    ColumnLayout {
                        width: reviewScroll.availableWidth; spacing: 16
                        PlainLabel { text: "You decide when an email or application match is uncertain."; color: "#6f806c" }
                        PlainLabel { visible: backend.reviews.length === 0; text: "All clear. Emails that need a second look will appear here."; color: "#8a9788"; Layout.topMargin: 50 }
                        Repeater {
                            model: backend.reviews
                            delegate: Card {
                                required property var modelData
                                Layout.fillWidth: true
                                ColumnLayout {
                                    anchors.fill: parent
                                    PlainLabel { text: modelData.subject; font.bold: true; Layout.fillWidth: true; wrapMode: Text.WordWrap; textFormat: Text.PlainText }
                                    PlainLabel { text: modelData.reason; color: "#b08045" }
                                    PlainLabel { visible: !!JSON.parse(modelData.proposed_json).extraction.company || !!JSON.parse(modelData.proposed_json).extraction.role; text: "Proposed: " + (JSON.parse(modelData.proposed_json).extraction.company || "Unknown company") + " / " + (JSON.parse(modelData.proposed_json).extraction.role || "Unknown role"); Layout.fillWidth: true; wrapMode: Text.WordWrap; color: "#61745e" }
                                    PlainLabel { text: modelData.sender; color: "#859280"; textFormat: Text.PlainText }
                                    PlainLabel { text: modelData.body.slice(0, 1200); Layout.fillWidth: true; wrapMode: Text.WordWrap; textFormat: Text.PlainText; color: "#61745e" }
                                    RowLayout {
                                        ComboBox { id: reviewApp; Layout.fillWidth: true; model: backend.applications.map(function(a) { return {id: a.id, name: a.company + " / " + a.role} }); textRole: "name"; valueRole: "id" }
                                        ActionButton { text: "Link application"; enabled: !backend.busy && reviewApp.currentIndex >= 0; onClicked: backend.resolveReview(modelData.id, reviewApp.currentValue, false) }
                                        ActionButton { text: "Create application"; visible: !!JSON.parse(modelData.proposed_json).extraction.company && !!JSON.parse(modelData.proposed_json).extraction.role; enabled: !backend.busy; onClicked: backend.resolveReview(modelData.id, 0, false) }
                                        ActionButton { text: "Add manually"; visible: !JSON.parse(modelData.proposed_json).extraction.company || !JSON.parse(modelData.proposed_json).extraction.role; enabled: !backend.busy; onClicked: root.openApplication(null) }
                                        ActionButton { text: "Ignore"; enabled: !backend.busy; onClicked: backend.resolveReview(modelData.id, 0, true) }
                                    }
                                }
                            }
                        }
                    }
                }
                // Email history
                ScrollView {
                    id: historyScroll
                    contentWidth: availableWidth
                    clip: true
                    ColumnLayout {
                        width: historyScroll.availableWidth; spacing: 20
                        Card {
                            Layout.fillWidth: true
                            ColumnLayout {
                                anchors.fill: parent; spacing: 15
                                PlainLabel { text: "Reconstruct a past job search"; font.bold: true; font.pixelSize: 20; color: "#2b4434" }
                                PlainLabel { text: "Scan connected mailboxes from oldest to newest. Preview first, then set your spending limit.\nRepeated scans reuse saved results. Email dates below use UTC."; color: "#788773"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                RowLayout {
                                    ComboBox { model: ["Last month", "Last 3 months", "Last 6 months", "Last year", "Custom"]; onActivated: { if (currentIndex < 4) scanStart.text = backend.historyStart([1, 3, 6, 12][currentIndex]) } }
                                    Field { id: scanStart; text: backend.historyStart(1); placeholderText: "Start YYYY-MM-DD" }
                                    PlainLabel { text: "to"; color: "#7d897b" }
                                    Field { id: scanEnd; text: Qt.formatDate(new Date(), "yyyy-MM-dd"); placeholderText: "End YYYY-MM-DD" }
                                    ActionButton { text: "Preview scan →"; enabled: !backend.busy; onClicked: backend.previewHistory(scanStart.text, scanEnd.text) }
                                }
                            }
                        }
                        PlainLabel { text: "Import history"; font.bold: true; font.pixelSize: 18; color: "#2b4434" }
                        Repeater {
                            model: backend.scans
                            delegate: Card {
                                required property var modelData
                                Layout.fillWidth: true
                                RowLayout {
                                    anchors.fill: parent
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        PlainLabel { text: modelData.start_at.slice(0, 10) + " → " + modelData.end_at.slice(0, 10); font.bold: true; color: "#39523b" }
                                        PlainLabel { text: modelData.state + " · estimated usage / reservations $" + modelData.spent.toFixed(4) + " USD"; color: "#83907e" }
                                        PlainLabel { text: modelData.processed + " processed · " + modelData.review_count + " for review · " + modelData.pending + " waiting · " + modelData.failed + " failed · " + modelData.unavailable + " unavailable"; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: "#61765b" }
                                        PlainLabel { visible: modelData.error.length > 0; text: modelData.error; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: "#965b38" }
                                    }
                                    Field { id: resumeBudget; text: modelData.budget.toString(); Layout.preferredWidth: 80; placeholderText: "Budget USD"; visible: modelData.state !== "completed" }
                                    ActionButton { text: "Resume"; visible: modelData.state !== "completed"; enabled: !backend.busy; onClicked: backend.resumeScan(modelData.id, Number(resumeBudget.text)) }
                                }
                            }
                        }
                    }
                }
                // Settings
                ScrollView {
                    id: settingsScroll
                    contentWidth: availableWidth
                    clip: true
                    ColumnLayout {
                        width: settingsScroll.availableWidth; spacing: 20
                        Card {
                            Layout.fillWidth: true
                            ColumnLayout {
                                anchors.fill: parent; spacing: 12
                                PlainLabel { text: "AI configuration"; font.bold: true; font.pixelSize: 20; color: "#2b4434" }
                                PlainLabel { text: backend.apiReady ? "● API key configured" : "○ Manual mode — add a key to enable AI"; color: "#438574" }
                                PlainLabel { text: "AI sends selected email text to OpenAI using your account. Keys are saved in your OS credential store.\nModel defaults: GPT-6 Luna (Decisions) + GPT-5.4 mini (extraction)."; wrapMode: Text.WordWrap; color: "#7b8975"; Layout.fillWidth: true }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Field { id: apiKey; placeholderText: "Paste your OpenAI API key"; echoMode: showKey.checked ? TextInput.Normal : TextInput.Password; Layout.fillWidth: true }
                                    CheckBox { id: showKey; text: "Show" }
                                    CheckBox { id: sessionOnly; text: "Session only" }
                                    ActionButton { text: "Save key"; enabled: !backend.busy && apiKey.text.length > 0; onClicked: { backend.saveKey(apiKey.text, !sessionOnly.checked); apiKey.clear() } }
                                    ActionButton { text: "Test"; enabled: !backend.busy && backend.apiReady; onClicked: backend.testKey() }
                                    ActionButton { text: "Remove"; enabled: !backend.busy && backend.apiReady; onClicked: backend.removeKey() }
                                }
                                RowLayout {
                                    CheckBox { id: autoSync; text: "Automatically process new emails every 5 minutes"; checked: backend.aiEnabled }
                                    Item { Layout.fillWidth: true }
                                    PlainLabel { text: "Per sync $"; color: "#7b8975" }
                                    Field { id: syncBudget; text: backend.syncBudget; Layout.preferredWidth: 65 }
                                    PlainLabel { text: "Daily $"; color: "#7b8975" }
                                    Field { id: dailyBudget; text: backend.dailyBudget; Layout.preferredWidth: 65 }
                                    ActionButton { text: "Apply"; enabled: !backend.busy; onClicked: backend.configureAI(autoSync.checked, syncBudget.text, dailyBudget.text) }
                                }
                            }
                        }
                        Card {
                            Layout.fillWidth: true
                            ColumnLayout {
                                anchors.fill: parent; spacing: 12
                                PlainLabel { text: "Connected mailboxes"; font.bold: true; font.pixelSize: 20; color: "#2b4434" }
                                PlainLabel { text: "Connect your account in your browser. Access is read-only.\nGoogle public verification and Microsoft publisher verification are pending."; wrapMode: Text.WordWrap; color: "#7b8975"; Layout.fillWidth: true }
                                RowLayout {
                                    ActionButton { text: backend.connectingProvider === "gmail" ? "Signing in to Gmail…" : "Connect Gmail"; enabled: !backend.busy && backend.googleConfigured; onClicked: { mailboxConsent.provider = "gmail"; mailboxConsent.open() } }
                                    ActionButton { text: backend.connectingProvider === "outlook" ? "Signing in to Outlook…" : "Connect Outlook"; enabled: !backend.busy && backend.microsoftClient.length > 0; onClicked: { mailboxConsent.provider = "outlook"; mailboxConsent.open() } }
                                    CheckBox { id: mailSession; text: "Session only" }
                                    Item { Layout.fillWidth: true }
                                    ActionButton { text: "Advanced OAuth setup"; enabled: !backend.busy; onClicked: advancedOAuth.open() }
                                }
                                PlainLabel { text: backend.mailboxStatuses.gmail; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: "#61765b" }
                                PlainLabel { text: backend.mailboxStatuses.outlook; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: "#61765b" }
                                PlainLabel { visible: !backend.googleConfigured; text: "Google sign-in is not included in this build. Configure a desktop client in Advanced OAuth setup."; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: "#965b38" }
                                Repeater {
                                    model: backend.accounts
                                    delegate: RowLayout {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        PlainLabel { text: modelData.address + " · " + modelData.provider + (modelData.connected ? " · connected" : " · reconnect required"); Layout.fillWidth: true; color: "#61765b" }
                                        ActionButton { text: "Disconnect"; enabled: !backend.busy && modelData.connected; onClicked: backend.disconnectAccount(modelData.id) }
                                    }
                                }
                            }
                        }
                        Card {
                            Layout.fillWidth: true
                            ColumnLayout {
                                anchors.fill: parent; spacing: 12
                                PlainLabel { text: "Records and storage"; font.bold: true; font.pixelSize: 20; color: "#2b4434" }
                                PlainLabel { text: backend.dataPath; wrapMode: Text.WrapAnywhere; color: "#7b8975"; Layout.fillWidth: true }
                                RowLayout {
                                    ActionButton { text: "Back up database"; enabled: !backend.busy; onClicked: backend.backupDatabase() }
                                    ActionButton { text: "Export this search"; enabled: !backend.busy; onClicked: backend.exportExcel() }
                                    ActionButton { text: root.search.archived ? "Unarchive search" : "Archive search"; enabled: !backend.busy; onClicked: backend.archiveSearch(!root.search.archived) }
                                }
                                PlainLabel { text: "Exports and backups exclude API keys. Keep database backups private: they include saved email text.\nClosing the window keeps the app in the tray when available. Quit from the tray to stop it."; wrapMode: Text.WordWrap; color: "#7b8975"; Layout.fillWidth: true }
                            }
                        }
                    }
                }
            }
        }
    }
    Dialog {
        id: mailboxConsent
        property string provider: ""
        title: provider === "gmail" ? "Connect Gmail" : "Connect Outlook"
        modal: true; anchors.centerIn: parent; width: 560
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: {
            if (provider === "gmail") backend.connectGmail(!mailSession.checked)
            else backend.connectOutlook(backend.microsoftClient, !mailSession.checked)
        }
        ColumnLayout {
            width: parent.width; spacing: 14
            PlainLabel { text: "Job Tracker AI reads email senders, subjects, dates, and message bodies to track your applications. It cannot send, delete, or mark emails as read. Saved email text and job records stay in a local database."; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            PlainLabel { text: "Connecting does not start AI processing. When you start a scan or enable automatic processing, selected email text is sent to OpenAI using your API key. This can include unrelated emails. No email data is sent to the app developer."; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            PlainLabel { text: "Continue to the provider's consent screen in your browser. Your account appears here only after sign-in and mailbox access succeed."; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: "#61765b" }
            ActionButton { text: "Read privacy policy"; onClicked: Qt.openUrlExternally(backend.privacyUrl) }
        }
    }
    Dialog {
        id: advancedOAuth
        title: "Advanced OAuth setup"
        modal: true; anchors.centerIn: parent; width: 620
        standardButtons: Dialog.Close
        ColumnLayout {
            width: parent.width; spacing: 14
            PlainLabel { text: "Use your own desktop registration for development or a fork. Normal sign-in uses the maintained registrations included in the app."; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            ActionButton { text: "Choose Google Desktop client JSON…"; enabled: !backend.busy; onClicked: backend.chooseGmailClient(!mailSession.checked) }
            Field { id: microsoftClient; text: backend.microsoftClient; placeholderText: "Microsoft public client ID"; Layout.fillWidth: true }
            ActionButton { text: "Save Microsoft client ID"; enabled: !backend.busy; onClicked: backend.saveMicrosoftClient(microsoftClient.text) }
            PlainLabel { text: "User API keys and OAuth tokens stay private. A desktop registration identifies the app; it cannot act as a confidential backend credential."; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: "#61765b" }
        }
    }
    Dialog {
        id: searchDialog; title: "Create a job search"; modal: true; anchors.centerIn: parent; width: 480
        standardButtons: Dialog.Save | Dialog.Cancel
        onAccepted: backend.createSearch(searchName.text, searchStart.text, searchEnd.text)
        ColumnLayout {
            anchors.fill: parent
            Field { id: searchName; placeholderText: "Name, e.g. 2026 Co-op"; Layout.fillWidth: true }
            Field { id: searchStart; placeholderText: "Start date YYYY-MM-DD (optional)"; Layout.fillWidth: true }
            Field { id: searchEnd; placeholderText: "End date YYYY-MM-DD (optional)"; Layout.fillWidth: true }
        }
    }
    Dialog {
        id: applicationDialog; title: root.selectedApp.id ? "Application details" : "Add an application"; modal: true
        anchors.centerIn: parent; width: 720; height: Math.min(root.height - 80, 760)
        standardButtons: Dialog.Save | Dialog.Cancel
        onAccepted: backend.saveApplication(JSON.stringify({company: company.text, role: role.text, applied_on: applied.text, requisition_id: requisition.text, stage: stage.currentText, outcome: outcome.currentText, notes: notes.text}), root.selectedApp.id || 0)
        ScrollView {
            id: applicationScroll
            contentWidth: availableWidth
            anchors.fill: parent; clip: true
            ColumnLayout {
                width: applicationScroll.availableWidth; spacing: 12
                Field { id: company; placeholderText: "Company *"; Layout.fillWidth: true }
                Field { id: role; placeholderText: "Role *"; Layout.fillWidth: true }
                RowLayout {
                    Field { id: applied; placeholderText: "Applied YYYY-MM-DD (if known)"; Layout.fillWidth: true }
                    Field { id: requisition; placeholderText: "Requisition ID"; Layout.fillWidth: true }
                }
                RowLayout {
                    ComboBox { id: stage; model: ["Applied", "Assessment", "Interview", "Offer"]; Layout.fillWidth: true }
                    ComboBox { id: outcome; model: ["Active", "Rejected", "Withdrawn", "Accepted", "Closed"]; Layout.fillWidth: true }
                }
                TextArea { id: notes; placeholderText: "Your notes"; wrapMode: Text.WordWrap; Layout.fillWidth: true; Layout.preferredHeight: 100 }
                PlainLabel { text: "Changing the status manually protects it from automatic email updates."; color: "#8c977f"; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 12 }
                RowLayout {
                    visible: !!root.selectedApp.id
                    ComboBox { id: moveSearch; model: backend.searches; textRole: "name"; valueRole: "id"; Layout.fillWidth: true }
                    ActionButton { text: "Move to search"; enabled: !backend.busy; onClicked: { backend.moveApplication(root.selectedApp.id, moveSearch.currentValue); applicationDialog.close() } }
                }
                PlainLabel { text: "EVENT TIMELINE"; visible: !!root.selectedApp.id; color: "#6d846a"; font.pixelSize: 11; Layout.topMargin: 12 }
                Repeater {
                    model: root.selectedApp.id ? backend.events : []
                    delegate: Frame {
                        required property var modelData
                        Layout.fillWidth: true
                        ColumnLayout {
                            anchors.fill: parent
                            PlainLabel { text: modelData.kind + " · " + modelData.effective_at.slice(0, 16) + " UTC"; color: "#438574" }
                            PlainLabel { text: modelData.evidence; wrapMode: Text.WordWrap; Layout.fillWidth: true; textFormat: Text.PlainText; color: "#81907b" }
                        }
                    }
                }
            }
        }
    }
    Dialog {
        id: importDialog; title: "Preview Excel import"; modal: true; anchors.centerIn: parent; width: 660
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: {
            var mapping = {}
            for (var i = 0; i < mappings.count; i++) mapping[mappings.itemAt(i).field] = mappings.itemAt(i).columnIndex
            backend.importExcel(JSON.stringify(mapping))
        }
        ColumnLayout {
            anchors.fill: parent
            PlainLabel { text: backend.importPreview.count + " rows found. Map columns below; duplicates are skipped."; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            Repeater {
                id: mappings
                model: [{field:"company", label:"Company *"}, {field:"role", label:"Role *"}, {field:"applied_on", label:"Applied date"}, {field:"stage", label:"Stage"}, {field:"outcome", label:"Outcome"}, {field:"requisition_id", label:"Requisition ID"}, {field:"notes", label:"Notes"}]
                delegate: RowLayout {
                    required property var modelData
                    property string field: modelData.field
                    property int columnIndex: column.currentIndex - 1
                    Layout.fillWidth: true
                    PlainLabel { text: modelData.label; Layout.preferredWidth: 160 }
                    ComboBox { id: column; model: ["Not mapped"].concat(backend.importPreview.headers); Layout.fillWidth: true }
                }
            }
            PlainLabel { text: "Preview: " + JSON.stringify(backend.importPreview.samples); Layout.fillWidth: true; wrapMode: Text.WordWrap; textFormat: Text.PlainText; color: "#83907e" }
            PlainLabel { text: "Dates: YYYY-MM-DD. Stages: Applied, Assessment, Interview, Offer.\nOutcomes: Active, Rejected, Withdrawn, Accepted, Closed. Leave incompatible columns unmapped."; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: "#83907e" }
        }
    }
    Dialog {
        id: scanDialog; title: "Review API usage before importing"; modal: true; anchors.centerIn: parent; width: 550
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: backend.startHistory(Number(historyBudget.text))
        ColumnLayout {
            anchors.fill: parent; spacing: 15
            PlainLabel { text: "Emails found: " + (backend.estimate.total || 0) + "\nEmails without saved classification: " + (backend.estimate.count || 0); color: "#405b43" }
            PlainLabel { text: "Illustrative estimate: $" + Number(backend.estimate.low || 0).toFixed(2) + "–$" + Number(backend.estimate.high || 0).toFixed(2) + " USD"; font.bold: true; color: "#216e62" }
            PlainLabel { text: "This scan sends email text to OpenAI and uses your API credits. Actual cost depends on message length, extraction volume and retries. Estimates use rates checked " + (backend.estimate.price_date || "") + ".\n\nWe reserve a conservative amount before each request. Failed requests may retain a reservation. The scan pauses when its budget cannot cover the next request."; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: "#7b8975" }
            Field { id: historyBudget; text: "1.00"; placeholderText: "Spending limit USD"; Layout.fillWidth: true }
        }
    }
}
