import QtQuick
import QtQuick.Controls

Button {
    id: control
    property bool primary: false
    implicitHeight: 40
    leftPadding: 16; rightPadding: 16
    background: Rectangle {
        radius: 8
        color: control.primary ? (control.down ? "#164c43" : "#216e62") : (control.hovered ? "#e5ece2" : "#f2f5ef")
        border.color: control.primary ? "#216e62" : "#dce4d7"
        opacity: control.enabled ? 1 : 0.5
    }
    contentItem: Label {
        text: control.text
        color: control.primary ? "white" : "#3e5b46"
        font.pixelSize: 12
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        opacity: control.enabled ? 1 : 0.5
    }
}
