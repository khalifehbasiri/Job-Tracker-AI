import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

ApplicationWindow {
    id: root
    width: 1360; height: 900
    minimumWidth: 1080; minimumHeight: 720
    visible: true
    title: "Job Tracker AI"
    color: Theme.background
    palette.window: Theme.surface
    palette.windowText: Theme.text
    palette.base: Theme.surface
    palette.text: Theme.text
    palette.button: Theme.button
    palette.buttonText: Theme.text
    palette.highlight: Theme.accent
    palette.highlightedText: Theme.dark ? "#12201d" : "white"
    palette.mid: Theme.border
    palette.dark: Theme.muted
    palette.light: Theme.surface
    palette.alternateBase: Theme.subtle
    palette.toolTipBase: Theme.surface
    palette.toolTipText: Theme.text
    Binding { target: Theme; property: "dark"; value: backend.darkMode }
    font.family: "Segoe UI"
    font.pixelSize: 14
    property int page: 0
    Component.onCompleted: { if (backend.setupNeeded) setupWizard.open() }
    Shortcut { sequence: "F1"; onActivated: backend.openSetupGuide() }
    property var selectedApp: ({})
    property var expandedReviews: []
    function toggleReview(id) {
        expandedReviews = expandedReviews.indexOf(id) >= 0
            ? expandedReviews.filter(function(value) { return value !== id })
            : expandedReviews.concat([id])
    }
    property var filteredReviews: backend.reviews.filter(function(item) {
        var proposal = JSON.parse(item.proposed_json)
        return [item.subject, item.sender, item.body, item.reason, proposal.kind,
                proposal.extraction.company || "", proposal.extraction.role || ""]
            .join(" ").toLowerCase().indexOf(reviewFilter.text.toLowerCase()) >= 0
    })
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
                Image { source: "../assets/logo.png"; Layout.preferredWidth: 54; Layout.preferredHeight: 54; fillMode: Image.PreserveAspectFit; Layout.topMargin: 8 }
                PlainLabel { text: "JOB TRACKER"; color: "#ffffff"; font.bold: true; font.pixelSize: 19 }
                PlainLabel { text: "A little clarity for your next move."; color: "#aac0b7"; font.pixelSize: 11; Layout.bottomMargin: 28 }
                Repeater {
                    model: ["Overview", "Applications", "Review inbox", "Email history", "Settings"]
                    delegate: ActionButton {
                        required property string modelData
                        required property int index
                        objectName: "navigation-" + index
                        text: modelData; Layout.fillWidth: true; implicitHeight: 46
                        onClicked: root.page = index
                        background: Rectangle { color: root.page === index ? "#2c5a4e" : "transparent"; radius: 9 }
                        contentItem: PlainLabel { text: parent.text; color: root.page === index ? "white" : "#bed1c7"; verticalAlignment: Text.AlignVCenter; leftPadding: 12 }
                    }
                }
                Item { Layout.fillHeight: true }
                ActionButton {
                    objectName: "openHelpButton"
                    text: "Help & setup guide · F1"; Layout.fillWidth: true
                    onClicked: backend.openSetupGuide()
                    ToolTip.visible: hovered
                    ToolTip.text: "Open the complete offline guide in your browser."
                    background: Rectangle { color: parent.hovered ? "#2c5a4e" : "transparent"; radius: 9 }
                    contentItem: PlainLabel { text: parent.text; color: "#d5e4db"; verticalAlignment: Text.AlignVCenter; leftPadding: 12 }
                }
                PlainLabel { text: "LOCAL FIRST"; color: "#aec9ba"; font.pixelSize: 10; font.letterSpacing: 2 }
                PlainLabel { text: "Your searches. Your records.\nYour API key."; color: "#d5e4db"; lineHeight: 1.4; font.pixelSize: 12 }
                Rectangle { Layout.fillWidth: true; height: 1; color: "#365d4e"; Layout.topMargin: 15 }
                PlainLabel { text: "v" + backend.appVersion + "  ·  Open source"; color: "#91b29f"; font.pixelSize: 11 }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            Layout.margins: 30; spacing: 20
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 6
                    PlainLabel { text: "YOUR NEXT CHAPTER"; color: Theme.muted; font.pixelSize: 10; font.letterSpacing: 2 }
                    PlainLabel { text: ["Search overview", "Your applications", "Review inbox", "Import email history", "Make it yours"][root.page]; font.pixelSize: 30; font.weight: Font.DemiBold; color: Theme.text }
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
                color: Theme.subtle; radius: 10
                RowLayout {
                    id: statusRow
                    anchors.fill: parent; anchors.margins: 12
                    BusyIndicator { running: backend.busy; visible: running; implicitWidth: 22; implicitHeight: 22 }
                    PlainLabel { id: statusText; objectName: "statusText"; text: backend.message; color: Theme.text; wrapMode: Text.WordWrap; Layout.fillWidth: true; Layout.alignment: Qt.AlignVCenter; font.pixelSize: 12 }
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
                            PlainLabel { text: root.search.name + (root.search.archived ? " · archived" : ""); color: Theme.text; font.pixelSize: 17 }
                            Item { Layout.fillWidth: true }
                            ActionButton { text: "+ Add application"; enabled: !backend.busy; onClicked: root.openApplication(null) }
                        }
                        RowLayout {
                            Layout.fillWidth: true; spacing: 14; uniformCellSizes: true
                            Stat { label: "APPLICATIONS"; value: backend.applications.length.toString(); Layout.fillWidth: true }
                            Stat { label: "ACTIVE"; value: backend.applications.filter(function(a) { return a.outcome === "Active" }).length.toString(); Layout.fillWidth: true }
                            Stat { label: "INTERVIEWS"; value: root.countStage("Interview").toString(); Layout.fillWidth: true; accent: Theme.warning }
                            Stat { label: "NEEDS REVIEW"; value: backend.reviews.length.toString(); Layout.fillWidth: true; accent: Theme.warning }
                        }
                        RowLayout {
                            Layout.fillWidth: true; spacing: 20; uniformCellSizes: true
                            Card {
                                Layout.fillWidth: true; Layout.preferredHeight: 245
                                ColumnLayout {
                                    anchors.fill: parent; spacing: 16
                                    PlainLabel { text: "Where things stand"; font.bold: true; font.pixelSize: 17; color: Theme.text }
                                    Repeater {
                                        model: ["Applied", "Assessment", "Interview", "Offer"]
                                        delegate: RowLayout {
                                            required property string modelData
                                            Layout.fillWidth: true
                                            PlainLabel { text: modelData; Layout.preferredWidth: 100; color: Theme.muted }
                                            Rectangle {
                                                Layout.fillWidth: true; height: 9; radius: 4; color: Theme.subtle
                                                Rectangle { width: parent.width * root.countStage(modelData) / Math.max(1, backend.applications.length); height: parent.height; radius: 4; color: Theme.accent }
                                            }
                                            PlainLabel { text: root.countStage(modelData); Layout.preferredWidth: 25; horizontalAlignment: Text.AlignRight; color: Theme.muted }
                                        }
                                    }
                                    Item { Layout.fillHeight: true }
                                }
                            }
                            Card {
                                Layout.fillWidth: true; Layout.preferredHeight: 245
                                ColumnLayout {
                                    anchors.fill: parent
                                    PlainLabel { text: "Coming up"; font.bold: true; font.pixelSize: 17; color: Theme.text }
                                    PlainLabel { visible: backend.tasks.filter(function(t) { return !t.completed }).length === 0; text: "No upcoming tasks yet.\nEmail invitations and deadlines appear here."; wrapMode: Text.WordWrap; color: Theme.muted; Layout.fillWidth: true; Layout.topMargin: 30 }
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
                                    PlainLabel { text: "Recent applications"; font.bold: true; font.pixelSize: 17; color: Theme.text }
                                    Item { Layout.fillWidth: true }
                                    ActionButton { text: "View all →"; flat: true; onClicked: root.page = 1 }
                                }
                                PlainLabel { visible: backend.applications.length === 0; text: "Start with a manual application, import your Excel tracker, or connect an email account."; wrapMode: Text.WordWrap; color: Theme.muted; Layout.fillWidth: true; Layout.margins: 20 }
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
                                PlainLabel { text: "COMPANY / ROLE"; Layout.fillWidth: true; color: Theme.muted; font.pixelSize: 11 }
                                PlainLabel { text: "STAGE"; Layout.preferredWidth: 110; color: Theme.muted; font.pixelSize: 11 }
                                PlainLabel { text: "OUTCOME"; Layout.preferredWidth: 110; color: Theme.muted; font.pixelSize: 11 }
                                PlainLabel { text: "APPLIED"; Layout.preferredWidth: 100; color: Theme.muted; font.pixelSize: 11 }
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
                                            PlainLabel { text: modelData.company; font.bold: true; color: Theme.text; Layout.fillWidth: true; elide: Text.ElideRight }
                                            PlainLabel { text: modelData.role; color: Theme.muted; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight }
                                        }
                                        PlainLabel { text: modelData.stage; Layout.preferredWidth: 110; color: Theme.accent }
                                        PlainLabel { text: modelData.outcome; Layout.preferredWidth: 110; color: modelData.outcome === "Rejected" ? Theme.danger : Theme.muted }
                                        PlainLabel { text: modelData.applied_on || "Unknown"; Layout.preferredWidth: 100; color: Theme.muted; font.pixelSize: 12 }
                                        PlainLabel { text: "Open →"; Layout.preferredWidth: 65; color: Theme.muted }
                                    }
                                }
                                PlainLabel { anchors.centerIn: parent; visible: root.filteredApps.length === 0; text: "No applications to show."; color: Theme.muted }
                            }
                        }
                    }
                }
                // Review inbox
                ColumnLayout {
                        spacing: 16
                        RowLayout {
                            Layout.fillWidth: true
                            Field { id: reviewFilter; objectName: "reviewFilter"; placeholderText: "Search subject, sender, company, role, or email text…"; Layout.fillWidth: true }
                            HelpTip { explanation: "Uncertain classifications and ambiguous matches stay here. Expand an email to link, create, or ignore a record. Search includes the full email body." }
                            ActionButton { text: "Collapse all"; onClicked: root.expandedReviews = [] }
                        }
                        PlainLabel { text: root.filteredReviews.length + " of " + backend.reviews.length + " emails · Click an email to expand it."; color: Theme.muted }
                        PlainLabel { visible: backend.reviews.length === 0; text: "All clear. Emails that need a second look will appear here."; color: Theme.muted; Layout.topMargin: 50 }
                        PlainLabel { visible: backend.reviews.length > 0 && root.filteredReviews.length === 0; text: "No emails match your search."; color: Theme.muted }
                        ListView {
                            id: reviewItems
                            objectName: "reviewList"
                            Layout.fillWidth: true; Layout.fillHeight: true
                            clip: true; spacing: 16; cacheBuffer: 200
                            ScrollBar.vertical: ScrollBar {}
                            model: root.filteredReviews
                            delegate: Card {
                                id: reviewCard
                                required property var modelData
                                property bool expanded: root.expandedReviews.indexOf(modelData.id) >= 0
                                property var proposal: JSON.parse(modelData.proposed_json)
                                objectName: "reviewCard-" + modelData.id
                                width: ListView.view.width
                                ColumnLayout {
                                    anchors.fill: parent
                                    Button {
                                        objectName: "reviewHeader-" + modelData.id
                                        Layout.fillWidth: true; padding: 0
                                        Accessible.name: modelData.subject + (reviewCard.expanded ? ", collapse email" : ", expand email")
                                        background: Rectangle { color: parent.hovered ? Theme.subtle : "transparent"; radius: 6 }
                                        onClicked: root.toggleReview(modelData.id)
                                        contentItem: RowLayout {
                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                PlainLabel { text: modelData.subject; font.bold: true; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                                                PlainLabel { text: modelData.sender + " · " + modelData.received_at.slice(0, 10) + " · " + reviewCard.proposal.kind; color: Theme.muted; Layout.fillWidth: true; elide: Text.ElideRight }
                                            }
                                            PlainLabel { text: reviewCard.expanded ? "⌃" : "⌄"; font.pixelSize: 22; color: Theme.accent }
                                        }
                                    }
                                    PlainLabel { text: modelData.reason; color: Theme.warning; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                    PlainLabel { visible: !!reviewCard.proposal.extraction.company || !!reviewCard.proposal.extraction.role; text: "Proposed: " + (reviewCard.proposal.extraction.company || "Unknown company") + " / " + (reviewCard.proposal.extraction.role || "Unknown role"); Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.muted }
                                    PlainLabel { objectName: "reviewBody-" + modelData.id; visible: reviewCard.expanded; text: reviewCard.expanded ? modelData.body : ""; Layout.fillWidth: true; wrapMode: Text.WordWrap; textFormat: Text.PlainText; color: Theme.muted }
                                    RowLayout {
                                        visible: reviewCard.expanded
                                        ComboBox { id: reviewApp; Layout.fillWidth: true; model: reviewCard.expanded ? backend.applications.map(function(a) { return {id: a.id, name: a.company + " / " + a.role} }) : []; textRole: "name"; valueRole: "id" }
                                        ActionButton { text: "Link application"; enabled: !backend.busy && reviewApp.currentIndex >= 0; onClicked: backend.resolveReview(modelData.id, reviewApp.currentValue, false) }
                                        ActionButton { text: "Create application"; visible: !!JSON.parse(modelData.proposed_json).extraction.company && !!JSON.parse(modelData.proposed_json).extraction.role; enabled: !backend.busy; onClicked: backend.resolveReview(modelData.id, 0, false) }
                                        ActionButton { text: "Add manually"; visible: !JSON.parse(modelData.proposed_json).extraction.company || !JSON.parse(modelData.proposed_json).extraction.role; enabled: !backend.busy; onClicked: root.openApplication(null) }
                                        ActionButton { text: "Ignore"; enabled: !backend.busy; onClicked: backend.resolveReview(modelData.id, 0, true) }
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
                                PlainLabel { text: "Reconstruct a past job search"; font.bold: true; font.pixelSize: 20; color: Theme.text }
                                RowLayout {
                                    PlainLabel { text: "Email source"; color: Theme.muted }
                                    ComboBox { objectName: "historyProviderSelector"; model: ["Gmail", "Outlook", "All mailboxes"]; currentIndex: ["gmail", "outlook", "all"].indexOf(backend.selectedProvider); enabled: !backend.busy; onActivated: backend.selectProvider(["gmail", "outlook", "all"][currentIndex]) }
                                }
                                PlainLabel { text: "Scan the selected email source from oldest to newest. This choice also controls automatic processing.\nExisting scans resume their original mailboxes. Preview first, then set your spending limit. Email dates use UTC."; color: Theme.muted; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                RowLayout {
                                    ComboBox { model: ["Last month", "Last 3 months", "Last 6 months", "Last year", "Custom"]; onActivated: { if (currentIndex < 4) scanStart.text = backend.historyStart([1, 3, 6, 12][currentIndex]) } }
                                    Field { id: scanStart; text: backend.historyStart(1); placeholderText: "Start YYYY-MM-DD" }
                                    PlainLabel { text: "to"; color: Theme.muted }
                                    Field { id: scanEnd; text: Qt.formatDate(new Date(), "yyyy-MM-dd"); placeholderText: "End YYYY-MM-DD" }
                                    ActionButton { text: "Preview scan →"; enabled: !backend.busy; onClicked: backend.previewHistory(scanStart.text, scanEnd.text) }
                                }
                            }
                        }
                        PlainLabel { text: "Import history"; font.bold: true; font.pixelSize: 18; color: Theme.text }
                        Repeater {
                            model: backend.scans
                            delegate: Card {
                                required property var modelData
                                Layout.fillWidth: true
                                RowLayout {
                                    anchors.fill: parent
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        PlainLabel { text: modelData.start_at.slice(0, 10) + " → " + modelData.end_at.slice(0, 10); font.bold: true; color: Theme.text }
                                        PlainLabel { text: modelData.state + " · estimated usage / reservations $" + modelData.spent.toFixed(4) + " USD"; color: Theme.muted }
                                        PlainLabel { text: modelData.processed + " processed · " + modelData.review_count + " for review · " + modelData.pending + " waiting · " + modelData.failed + " failed · " + modelData.unavailable + " unavailable"; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.muted }
                                        PlainLabel { visible: modelData.error.length > 0; text: modelData.error; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.warning }
                                    }
                                    Field { id: resumeBudget; text: modelData.budget.toString(); Layout.preferredWidth: 80; placeholderText: "Budget USD"; visible: modelData.state !== "completed" && modelData.state !== "running" }
                                    ActionButton { objectName: "resumeImport-" + modelData.id; text: "Resume"; visible: modelData.state !== "completed" && modelData.state !== "running"; enabled: !backend.busy; onClicked: backend.resumeScan(modelData.id, Number(resumeBudget.text)) }
                                    ActionButton { text: "Remove"; enabled: !backend.busy && modelData.state !== "running"; onClicked: backend.removeImport(modelData.id); ToolTip.visible: hovered; ToolTip.text: "Hide this import entry. Applications, saved emails and usage history are kept. Pause a running scan first." }
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
                            RowLayout {
                                anchors.fill: parent
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    PlainLabel { text: "Appearance"; font.bold: true; font.pixelSize: 20 }
                                    PlainLabel { text: "Choose a comfortable theme. Your preference is saved on this computer."; color: Theme.muted; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                }
                                Switch { objectName: "darkModeToggle"; text: "Dark mode"; checked: backend.darkMode; onToggled: backend.setDarkMode(checked) }
                            }
                        }
                        Card {
                            Layout.fillWidth: true
                            RowLayout {
                                anchors.fill: parent
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    PlainLabel { text: "Current job search"; font.bold: true; font.pixelSize: 20 }
                                    PlainLabel { text: root.search.name + (root.search.archived ? " · archived" : ""); color: Theme.accent; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                    PlainLabel { text: (root.search.start_date || "No start date") + " → " + (root.search.end_date || "No end date"); color: Theme.muted }
                                }
                                HelpTip { explanation: "A search groups your records and has its own Excel export. Dates are labels; they do not restrict email scans or move records. Archiving stops automatic processing for this search." }
                                ActionButton { text: "Edit search"; enabled: !backend.busy; onClicked: { editSearchName.text = root.search.name; editSearchStart.text = root.search.start_date; editSearchEnd.text = root.search.end_date; editSearchArchived.checked = root.search.archived; editSearchDialog.open() } }
                            }
                        }
                        Card {
                            Layout.fillWidth: true
                            ColumnLayout {
                                anchors.fill: parent; spacing: 12
                                RowLayout {
                                    PlainLabel { text: "AI configuration"; font.bold: true; font.pixelSize: 20; color: Theme.text }
                                    HelpTip { explanation: "You supply your own OpenAI API key and API credits. Click for a short setup guide."; onClicked: authHelp.open() }
                                }
                                PlainLabel { text: backend.apiReady ? "● API key configured" : "○ Manual mode — add a key to enable AI"; color: Theme.accent }
                                PlainLabel { text: "Supply your own OpenAI API key. API billing is separate from ChatGPT.\nAI sends selected email text to OpenAI using your account. Models: GPT-6 Luna (Decisions, provider public beta) + GPT-5.4 mini (extraction)."; wrapMode: Text.WordWrap; color: Theme.muted; Layout.fillWidth: true }
                                RowLayout {
                                    ActionButton { text: "Create an OpenAI key ↗"; onClicked: Qt.openUrlExternally("https://platform.openai.com/api-keys") }
                                    ActionButton { text: "Step-by-step setup"; onClicked: backend.openSetupGuide() }
                                    ActionButton { text: "Setup wizard"; enabled: !backend.busy; onClicked: { setupWizard.step = 0; setupWizard.open() } }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Field { id: apiKey; placeholderText: "Paste your OpenAI API key"; echoMode: showKey.checked ? TextInput.Normal : TextInput.Password; Layout.fillWidth: true }
                                    CheckBox { id: showKey; text: "Show" }
                                    CheckBox { id: sessionOnly; text: "Session only" }
                                    ActionButton { text: "Save key"; enabled: !backend.busy && apiKey.text.length > 0; onClicked: { backend.saveKey(apiKey.text, !sessionOnly.checked); apiKey.clear() } }
                                    ActionButton { text: "Check key"; enabled: !backend.busy && backend.apiReady; onClicked: backend.testKey() }
                                    ActionButton { text: "Remove"; enabled: !backend.busy && backend.apiReady; onClicked: backend.removeKey() }
                                }
                                RowLayout {
                                    CheckBox { id: autoSync; text: "Automatically process new emails every 5 minutes"; checked: backend.aiEnabled }
                                    Item { Layout.fillWidth: true }
                                    PlainLabel { text: "Per sync $"; color: Theme.muted }
                                    Field { id: syncBudget; text: backend.syncBudget; Layout.preferredWidth: 65 }
                                    PlainLabel { text: "Daily $"; color: Theme.muted }
                                    Field { id: dailyBudget; text: backend.dailyBudget; Layout.preferredWidth: 65 }
                                    HelpTip { explanation: "Limits are estimated USD usage plus reservations for in-flight or failed requests. Check OpenAI billing for actual charges. Automatic processing must be enabled explicitly." }
                                    ActionButton { text: "Apply"; enabled: !backend.busy; onClicked: backend.configureAI(autoSync.checked, syncBudget.text, dailyBudget.text) }
                                }
                            }
                        }
                        Card {
                            Layout.fillWidth: true
                            ColumnLayout {
                                anchors.fill: parent; spacing: 12
                                RowLayout {
                                    PlainLabel { text: "Connected mailboxes"; font.bold: true; font.pixelSize: 20; color: Theme.text }
                                    HelpTip { explanation: "This release uses your own Google or Microsoft OAuth registration. Click for the setup summary."; onClicked: authHelp.open() }
                                }
                                PlainLabel { text: "Use your own Google Desktop OAuth JSON or Microsoft application client ID. Shared one-click OAuth onboarding is not included.\nConnect in your browser after configuring your registration. Access is read-only."; wrapMode: Text.WordWrap; color: Theme.muted; Layout.fillWidth: true }
                                RowLayout {
                                    ComboBox { objectName: "settingsProviderSelector"; model: ["Gmail", "Outlook", "All mailboxes"]; currentIndex: ["gmail", "outlook", "all"].indexOf(backend.selectedProvider); enabled: !backend.busy; onActivated: backend.selectProvider(["gmail", "outlook", "all"][currentIndex]) }
                                    ActionButton { visible: backend.selectedProvider !== "outlook"; text: backend.connectingProvider === "gmail" ? "Signing in to Gmail…" : "Connect Gmail"; enabled: !backend.busy && backend.googleConfigured; onClicked: { mailboxConsent.provider = "gmail"; mailboxConsent.open() } }
                                    ActionButton { visible: backend.selectedProvider !== "gmail"; text: backend.connectingProvider === "outlook" ? "Signing in to Outlook…" : "Connect Outlook"; enabled: !backend.busy && backend.microsoftClient.length > 0; onClicked: { mailboxConsent.provider = "outlook"; mailboxConsent.open() } }
                                    CheckBox { id: mailSession; text: "Session only" }
                                    Item { Layout.fillWidth: true }
                                    ActionButton { text: "Configure your OAuth app"; enabled: !backend.busy; onClicked: advancedOAuth.open() }
                                }
                                PlainLabel { visible: backend.selectedProvider !== "outlook"; text: backend.mailboxStatuses.gmail; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.muted }
                                PlainLabel { visible: backend.selectedProvider !== "gmail"; text: backend.mailboxStatuses.outlook; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.muted }
                                PlainLabel { visible: backend.selectedProvider !== "outlook" && !backend.googleConfigured; text: "Gmail: import your Desktop OAuth JSON using Configure your OAuth app."; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.warning }
                                PlainLabel { visible: backend.selectedProvider !== "gmail" && !backend.microsoftClient.length; text: "Outlook: enter your Application (client) ID using Configure your OAuth app."; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.warning }
                                Repeater {
                                    model: backend.accounts.filter(function(a) { return backend.selectedProvider === "all" || a.provider === backend.selectedProvider })
                                    delegate: RowLayout {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        PlainLabel { text: modelData.address + " · " + modelData.provider + (modelData.connected ? " · connected" : " · reconnect required"); Layout.fillWidth: true; color: Theme.muted }
                                        ActionButton { text: "Reconnect"; enabled: !backend.busy && (modelData.provider === "gmail" ? backend.googleConfigured : backend.microsoftClient.length > 0); onClicked: { mailboxConsent.provider = modelData.provider; mailboxConsent.open() } }
                                        ActionButton { text: "Disconnect"; enabled: !backend.busy && modelData.connected; onClicked: backend.disconnectAccount(modelData.id) }
                                    }
                                }
                            }
                        }
                        Card {
                            Layout.fillWidth: true
                            ColumnLayout {
                                anchors.fill: parent; spacing: 12
                                PlainLabel { text: "Records and storage"; font.bold: true; font.pixelSize: 20; color: Theme.text }
                                PlainLabel { text: backend.dataPath; wrapMode: Text.WrapAnywhere; color: Theme.muted; Layout.fillWidth: true }
                                RowLayout {
                                    ActionButton { text: "Back up database"; enabled: !backend.busy; onClicked: backend.backupDatabase() }
                                    ActionButton { text: "Export this search"; enabled: !backend.busy; onClicked: backend.exportExcel() }
                                    ActionButton { text: root.search.archived ? "Unarchive search" : "Archive search"; enabled: !backend.busy; onClicked: backend.archiveSearch(!root.search.archived) }
                                }
                                PlainLabel { text: "Exports and backups exclude API keys. Keep database backups private: they include saved email text.\nClosing the window quits the app and stops automatic processing. Minimize the window to keep it running."; wrapMode: Text.WordWrap; color: Theme.muted; Layout.fillWidth: true }
                            }
                        }
                        Card {
                            Layout.fillWidth: true
                            ColumnLayout {
                                anchors.fill: parent; spacing: 12
                                PlainLabel { text: "About Job Tracker AI · v" + backend.appVersion; font.bold: true; font.pixelSize: 20; color: Theme.text }
                                PlainLabel { text: "MIT-licensed application with dynamically linked Qt/PySide6 under LGPL-3.0. License texts and dependency notices are included with the app; matching library sources are available with each release."; wrapMode: Text.WordWrap; color: Theme.muted; Layout.fillWidth: true }
                                ActionButton { text: "Licenses & library sources ↗"; onClicked: Qt.openUrlExternally(backend.licenseUrl) }
                            }
                        }
                    }
                }
            }
        }
    }
    Dialog {
        id: authHelp; objectName: "authHelp"
        title: "Connect your email and AI"; modal: true; anchors.centerIn: parent; width: 650
        standardButtons: Dialog.Close
        ColumnLayout {
            width: parent.width; spacing: 14
            PlainLabel { text: "You create your own credentials. Manual tracking needs none."; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.accent }
            PlainLabel { text: "1. OpenAI: create a project API key at platform.openai.com, configure API billing, then paste it in Settings → Save key → Check key. ChatGPT subscriptions do not include API credits."; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            PlainLabel { text: "2. Gmail: create a Google Cloud project, enable Gmail API, configure External consent in Testing, add yourself as a test user and add gmail.readonly. Create a Desktop app OAuth client and download its JSON. In Configure your OAuth app, import the JSON, then Connect Gmail."; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            PlainLabel { text: "3. Outlook: register an app in Microsoft Entra supporting organizational and personal accounts. Add Mobile and desktop → http://localhost, plus delegated Graph Mail.Read and User.Read permissions. Paste the Application (client) ID in Configure your OAuth app, save it, then Connect Outlook. No client secret is needed."; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            PlainLabel { text: "4. Pick Gmail, Outlook, or all mailboxes. In Email history, preview a date range and set a USD limit before starting. Connecting alone does not start a scan. Session-only credentials disappear when you quit."; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            ActionButton { text: "Open full offline setup guide"; onClicked: backend.openSetupGuide() }
            ActionButton { text: "Read the guide on GitHub ↗"; onClicked: Qt.openUrlExternally(backend.setupGuideUrl) }
        }
    }
    Dialog {
        id: editSearchDialog; objectName: "editSearchDialog"
        title: "Edit current job search"; modal: true; anchors.centerIn: parent; width: 520
        closePolicy: Popup.NoAutoClose
        ColumnLayout {
            width: parent.width; spacing: 12
            PlainLabel { text: "Name" }
            Field { id: editSearchName; Layout.fillWidth: true }
            PlainLabel { text: "Start and end dates (optional, YYYY-MM-DD)" }
            Field { id: editSearchStart; placeholderText: "Start date"; Layout.fillWidth: true }
            Field { id: editSearchEnd; placeholderText: "End date"; Layout.fillWidth: true }
            CheckBox { id: editSearchArchived; text: "Archived (pause automatic processing)" }
            PlainLabel { text: "Edits preserve all records. Exported Excel snapshots keep their original names and data.\n" + backend.message; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            RowLayout {
                ActionButton { text: "Cancel"; onClicked: editSearchDialog.close() }
                ActionButton { text: "Save"; primary: true; enabled: !backend.busy; onClicked: { if (backend.editSearch(editSearchName.text, editSearchStart.text, editSearchEnd.text, editSearchArchived.checked)) editSearchDialog.close() } }
            }
        }
    }
    Dialog {
        id: setupWizard
        objectName: "setupWizard"
        property int step: 0
        title: "Welcome · " + ["Your job search", "Your email", "Your OpenAI key", "Automatic processing"][step]
        modal: true; anchors.centerIn: parent; width: 680
        closePolicy: Popup.NoAutoClose
        ColumnLayout {
            width: parent.width; spacing: 14
            PlainLabel { text: "Bring your own credentials. Manual tracking is available without email or AI."; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.muted }
            PlainLabel { text: backend.message; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            StackLayout {
                currentIndex: setupWizard.step; Layout.fillWidth: true
                ColumnLayout {
                    PlainLabel { text: "Name this search, for example 2026 Co-op. You can create separate searches later."; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Field { id: initialSearchName; text: root.search.name; Layout.fillWidth: true }
                }
                ColumnLayout {
                    PlainLabel { text: "Create your own OAuth registration using the setup guide. Import Google's Desktop JSON, or paste Microsoft's Application (client) ID. Connecting grants read-only access and does not start a scan."; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    ComboBox { model: ["Gmail", "Outlook"]; currentIndex: backend.selectedProvider === "outlook" ? 1 : 0; enabled: !backend.busy; onActivated: backend.selectProvider(currentIndex === 0 ? "gmail" : "outlook") }
                    CheckBox { id: wizardMailSession; text: "Store email credentials for this session only"; onToggled: mailSession.checked = checked }
                    ActionButton { visible: backend.selectedProvider !== "outlook"; text: "Import Google Desktop JSON…"; enabled: !backend.busy; onClicked: backend.chooseGmailClient(!wizardMailSession.checked) }
                    Field { id: wizardMicrosoft; visible: backend.selectedProvider === "outlook"; text: backend.microsoftClient; placeholderText: "Application (client) ID"; Layout.fillWidth: true }
                    ActionButton { visible: backend.selectedProvider === "outlook"; text: "Save Microsoft client ID"; enabled: !backend.busy; onClicked: backend.saveMicrosoftClient(wizardMicrosoft.text) }
                    ActionButton { text: "Connect " + (backend.selectedProvider === "outlook" ? "Outlook" : "Gmail"); enabled: !backend.busy && (backend.selectedProvider === "outlook" ? backend.microsoftClient.length > 0 : backend.googleConfigured); onClicked: { mailboxConsent.provider = backend.selectedProvider === "outlook" ? "outlook" : "gmail"; mailboxConsent.open() } }
                    PlainLabel { text: backend.mailboxStatuses[backend.selectedProvider === "outlook" ? "outlook" : "gmail"]; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                }
                ColumnLayout {
                    PlainLabel { text: "Create a project API key in OpenAI Platform and configure API billing. ChatGPT subscriptions do not include API credits. Model/Decisions availability depends on your project."; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    ActionButton { text: "Create an OpenAI key ↗"; onClicked: Qt.openUrlExternally("https://platform.openai.com/api-keys") }
                    Field { id: wizardKey; placeholderText: "Paste your OpenAI API key"; echoMode: TextInput.Password; Layout.fillWidth: true }
                    CheckBox { id: wizardKeySession; text: "Store API key for this session only" }
                    RowLayout {
                        ActionButton { text: "Save key"; enabled: !backend.busy && wizardKey.text.length > 0; onClicked: { backend.saveKey(wizardKey.text, !wizardKeySession.checked); wizardKey.clear() } }
                        ActionButton { text: "Check key"; enabled: !backend.busy && backend.apiReady; onClicked: backend.testKey() }
                    }
                    PlainLabel { text: backend.apiReady ? "API key configured. Check key verifies extraction-model access without processing email." : "You can skip AI setup and use manual tracking."; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                }
                ColumnLayout {
                    PlainLabel { text: "When enabled, the app checks your selected email source every five minutes while running. Selected email text goes to OpenAI and uses your API credits. Leave this off to scan only when you choose."; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    CheckBox { id: wizardAuto; text: "Enable automatic email processing"; checked: backend.aiEnabled; enabled: backend.apiReady && backend.accounts.some(function(a) { return a.connected && (backend.selectedProvider === "all" || a.provider === backend.selectedProvider) }) }
                    RowLayout {
                        PlainLabel { text: "Per sync USD" }
                        Field { id: wizardSyncBudget; text: backend.syncBudget; Layout.preferredWidth: 90 }
                        PlainLabel { text: "Per day USD" }
                        Field { id: wizardDailyBudget; text: backend.dailyBudget; Layout.preferredWidth: 90 }
                    }
                }
            }
            ActionButton { text: "Open full step-by-step setup guide"; onClicked: backend.openSetupGuide() }
            RowLayout {
                Layout.fillWidth: true
                ActionButton { text: "Set up later"; enabled: !backend.busy; onClicked: { backend.finishSetup(); setupWizard.close() } }
                Item { Layout.fillWidth: true }
                ActionButton { text: "Back"; visible: setupWizard.step > 0; enabled: !backend.busy; onClicked: setupWizard.step-- }
                ActionButton {
                    text: setupWizard.step === 3 ? "Finish" : "Next"
                    enabled: !backend.busy && (setupWizard.step !== 3 || (Number(wizardSyncBudget.text) > 0 && Number(wizardSyncBudget.text) <= 10000 && Number(wizardDailyBudget.text) > 0 && Number(wizardDailyBudget.text) <= 10000))
                    onClicked: {
                        if (setupWizard.step === 0 && !backend.nameInitialSearch(initialSearchName.text)) return
                        if (setupWizard.step < 3) setupWizard.step++
                        else { backend.configureAI(wizardAuto.enabled && wizardAuto.checked, wizardSyncBudget.text, wizardDailyBudget.text); backend.finishSetup(); setupWizard.close() }
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
            PlainLabel { text: "Continue to the provider's consent screen in your browser. Your account appears here only after sign-in and mailbox access succeed."; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.muted }
            ActionButton { text: "Read privacy policy"; onClicked: Qt.openUrlExternally(backend.privacyUrl) }
        }
    }
    Dialog {
        id: advancedOAuth
        title: "Configure your own OAuth app"
        modal: true; anchors.centerIn: parent; width: 620
        standardButtons: Dialog.Close
        ColumnLayout {
            width: parent.width; spacing: 14
            PlainLabel { text: "Follow the full setup guide to create your own registration, then import Google Desktop JSON or save a Microsoft client ID. No project-owned email credentials are bundled."; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            ActionButton { text: "Open step-by-step setup guide"; onClicked: backend.openSetupGuide() }
            ActionButton { text: "Choose Google Desktop client JSON…"; enabled: !backend.busy; onClicked: backend.chooseGmailClient(!mailSession.checked) }
            Field { id: microsoftClient; text: backend.microsoftClient; placeholderText: "Microsoft public client ID"; Layout.fillWidth: true }
            ActionButton { text: "Save Microsoft client ID"; enabled: !backend.busy; onClicked: backend.saveMicrosoftClient(microsoftClient.text) }
            PlainLabel { text: "User API keys and OAuth tokens stay private. A desktop registration identifies the app; it cannot act as a confidential backend credential."; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.muted }
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
                    HelpTip { explanation: "Only application confirmations fill a blank applied date: explicit date first, otherwise the email's UTC received date. Rejection/interview emails leave it unknown. You can enter the actual submission date here." }
                }
                RowLayout {
                    ComboBox { id: stage; model: ["Applied", "Assessment", "Interview", "Offer"]; Layout.fillWidth: true }
                    ComboBox { id: outcome; model: ["Active", "Rejected", "Withdrawn", "Accepted", "Closed"]; Layout.fillWidth: true }
                    HelpTip { explanation: "Stage tracks progress (Applied → Offer). Outcome tracks whether the application is active or ended. For example, an interview rejection keeps stage Interview and sets outcome Rejected." }
                }
                TextArea { id: notes; placeholderText: "Your notes"; wrapMode: Text.WordWrap; Layout.fillWidth: true; Layout.preferredHeight: 100 }
                PlainLabel { text: "Changing the status manually protects it from automatic email updates."; color: Theme.muted; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 12 }
                RowLayout {
                    visible: !!root.selectedApp.id
                    ComboBox { id: moveSearch; model: backend.searches; textRole: "name"; valueRole: "id"; Layout.fillWidth: true }
                    ActionButton { text: "Move to search"; enabled: !backend.busy; onClicked: { backend.moveApplication(root.selectedApp.id, moveSearch.currentValue); applicationDialog.close() } }
                }
                PlainLabel { text: "EVENT TIMELINE"; visible: !!root.selectedApp.id; color: Theme.muted; font.pixelSize: 11; Layout.topMargin: 12 }
                Repeater {
                    model: root.selectedApp.id ? backend.events : []
                    delegate: Frame {
                        required property var modelData
                        Layout.fillWidth: true
                        ColumnLayout {
                            anchors.fill: parent
                            PlainLabel { text: modelData.kind + " · " + modelData.effective_at.slice(0, 16) + " UTC"; color: Theme.accent }
                            PlainLabel { text: modelData.evidence; wrapMode: Text.WordWrap; Layout.fillWidth: true; textFormat: Text.PlainText; color: Theme.muted }
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
            PlainLabel { text: "Preview: " + JSON.stringify(backend.importPreview.samples); Layout.fillWidth: true; wrapMode: Text.WordWrap; textFormat: Text.PlainText; color: Theme.muted }
            PlainLabel { text: "Dates: YYYY-MM-DD. Stages: Applied, Assessment, Interview, Offer.\nOutcomes: Active, Rejected, Withdrawn, Accepted, Closed. Leave incompatible columns unmapped."; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.muted }
        }
    }
    Dialog {
        id: scanDialog; title: "Review API usage before importing"; modal: true; anchors.centerIn: parent; width: 550
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: backend.startHistory(Number(historyBudget.text))
        ColumnLayout {
            anchors.fill: parent; spacing: 15
            PlainLabel { text: "Emails found: " + (backend.estimate.total || 0) + "\nEmails without saved classification: " + (backend.estimate.count || 0); color: Theme.text }
            PlainLabel { text: "Illustrative estimate: $" + Number(backend.estimate.low || 0).toFixed(2) + "–$" + Number(backend.estimate.high || 0).toFixed(2) + " USD"; font.bold: true; color: Theme.accent }
            PlainLabel { text: "This scan sends email text to OpenAI and uses your API credits. Actual cost depends on message length, extraction volume and retries. Estimates use rates checked " + (backend.estimate.price_date || "") + ".\n\nWe reserve a conservative amount before each request. Failed requests may retain a reservation. The scan pauses when its budget cannot cover the next request."; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.muted }
            Field { id: historyBudget; text: "1.00"; placeholderText: "Spending limit USD"; Layout.fillWidth: true }
        }
    }
}
