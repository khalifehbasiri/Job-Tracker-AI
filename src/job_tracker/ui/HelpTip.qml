import QtQuick
import QtQuick.Controls

ToolButton {
    id: control
    property string explanation: ""
    text: "ⓘ"
    implicitWidth: 30; implicitHeight: 30
    Accessible.name: explanation
    ToolTip.visible: hovered || activeFocus
    ToolTip.delay: 350
    ToolTip.text: explanation
    contentItem: PlainLabel {
        text: control.text; color: Theme.accent
        font.pixelSize: 18
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
    }
}
