import QtQuick
import "."
import QtQuick.Controls

Button {
    id: control
    property bool primary: false
    implicitHeight: 40
    leftPadding: 16; rightPadding: 16
    background: Rectangle {
        radius: 8
        color: control.primary ? (control.down ? (Theme.dark ? "#68b397" : "#164c43") : Theme.accent) : (control.hovered ? Theme.hover : Theme.button)
        border.color: control.primary ? Theme.accent : Theme.border
        opacity: control.enabled ? 1 : 0.5
    }
    contentItem: Label {
        text: control.text
        color: control.primary ? (Theme.dark ? Theme.background : "white") : Theme.text
        font.pixelSize: 12
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        opacity: control.enabled ? 1 : 0.5
    }
}
