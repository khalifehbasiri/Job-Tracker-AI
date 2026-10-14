import QtQuick
import "."
import QtQuick.Controls
import QtQuick.Layouts

Card {
    property string label
    property string value
    property color accent: Theme.text
    property bool highlighted: false
    implicitHeight: 116
    background: Rectangle { radius: 10; color: highlighted ? Theme.selected : Theme.surface }
    ColumnLayout {
        anchors.fill: parent
        spacing: 8
        PlainLabel { text: label; color: highlighted ? Theme.selectedText : Theme.muted; font.pixelSize: 13 }
        PlainLabel { text: value; color: highlighted ? Theme.selectedText : accent; font.pixelSize: 40; font.weight: Font.DemiBold }
    }
}
