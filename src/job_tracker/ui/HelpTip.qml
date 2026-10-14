import QtQuick
import QtQuick.Controls

ToolButton {
    id: control
    property string explanation: ""
    text: "i"
    implicitWidth: 30; implicitHeight: 30
    Accessible.name: explanation
    ToolTip.visible: hovered || activeFocus
    ToolTip.delay: 350
    ToolTip.text: explanation
    contentItem: PlainLabel {
        text: control.text; color: Theme.accent
        font.pixelSize: 14; font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: 15
        color: control.hovered ? Theme.hover : "transparent"
        border.width: control.visualFocus ? 2 : 1
        border.color: control.visualFocus ? Theme.accent : Theme.border
    }
}
