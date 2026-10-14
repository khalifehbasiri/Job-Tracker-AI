import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

ItemDelegate {
    id: control
    required property var application
    implicitHeight: 70
    leftPadding: 12; rightPadding: 12
    hoverEnabled: true
    Accessible.name: application.company + ", " + application.role + ", " + application.stage + ", " + application.outcome
    background: Rectangle {
        radius: 6
        color: control.hovered || control.down ? Theme.button : "transparent"
        border.width: control.visualFocus ? 2 : 0
        border.color: Theme.accent
    }
    contentItem: RowLayout {
        spacing: 14
        Rectangle {
            Layout.preferredWidth: 36; Layout.preferredHeight: 36
            radius: 7; color: Theme.subtle
            PlainLabel {
                anchors.centerIn: parent
                text: control.application.company.slice(0, 1).toUpperCase()
                color: Theme.accent; font.pixelSize: 16; font.weight: Font.DemiBold
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 4
            PlainLabel { text: control.application.company; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
            PlainLabel { text: control.application.role; color: Theme.muted; font.pixelSize: 13; Layout.fillWidth: true; elide: Text.ElideRight }
        }
        Item {
            Layout.preferredWidth: 100; Layout.fillHeight: true
            StatusTag { anchors.verticalCenter: parent.verticalCenter; text: control.application.stage }
        }
        PlainLabel {
            text: control.application.outcome
            Layout.preferredWidth: 88
            color: control.application.outcome === "Rejected" ? Theme.danger : Theme.muted
            font.pixelSize: 13
        }
        PlainLabel { text: control.application.applied_on || "Unknown"; Layout.preferredWidth: 90; color: Theme.muted; font.pixelSize: 13 }
        PlainLabel { text: "→"; color: control.hovered ? Theme.accent : Theme.muted; font.pixelSize: 18 }
    }
}
