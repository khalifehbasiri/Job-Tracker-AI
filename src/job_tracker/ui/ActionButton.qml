import QtQuick
import "."
import QtQuick.Controls

Button {
    id: control
    property bool primary: false
    implicitHeight: 42
    hoverEnabled: true
    leftPadding: 16; rightPadding: 16
    background: Rectangle {
        radius: 6
        color: control.primary ? (control.down ? Theme.accentPressed : Theme.accent)
            : (control.down || control.hovered ? Theme.hover : (control.flat ? "transparent" : Theme.button))
        border.width: control.visualFocus ? 2 : 0
        border.color: Theme.text
        opacity: control.enabled ? 1 : 0.45
    }
    contentItem: Label {
        text: control.text
        color: control.primary ? Theme.accentText : Theme.text
        font.pixelSize: 13
        font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        opacity: control.enabled ? 1 : 0.5
    }
}
