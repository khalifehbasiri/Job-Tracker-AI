import QtQuick
import "."
import QtQuick.Controls

TextField {
    id: control
    implicitHeight: 40
    padding: 12
    color: Theme.text
    placeholderTextColor: Theme.muted
    background: Rectangle {
        radius: 8
        color: Theme.surface
        border.color: control.activeFocus ? Theme.accent : Theme.border
    }
}
