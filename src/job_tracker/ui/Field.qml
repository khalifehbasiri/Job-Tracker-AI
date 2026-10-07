import QtQuick
import QtQuick.Controls

TextField {
    id: control
    implicitHeight: 40
    padding: 12
    color: "#2e4937"
    placeholderTextColor: "#8c9785"
    background: Rectangle {
        radius: 8
        color: "white"
        border.color: control.activeFocus ? "#438574" : "#dce4d7"
    }
}
