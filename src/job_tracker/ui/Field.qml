import QtQuick
import "."
import QtQuick.Controls

TextField {
    id: control
    implicitHeight: 42
    padding: 12
    font.pixelSize: 14
    selectByMouse: true
    color: Theme.text
    placeholderTextColor: Theme.muted
    background: Rectangle {
        radius: 6
        color: Theme.surface
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? Theme.accent : Theme.border
    }
}
