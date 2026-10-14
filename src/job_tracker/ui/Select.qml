import QtQuick
import QtQuick.Controls
import "."

ComboBox {
    id: control
    implicitHeight: 42
    implicitWidth: Math.max(150, implicitContentWidth + 54)
    leftPadding: 12
    rightPadding: 34
    font.pixelSize: 13
    background: Rectangle {
        radius: 6
        color: control.hovered ? Theme.button : Theme.surface
        border.width: control.visualFocus ? 2 : 1
        border.color: control.visualFocus ? Theme.accent : Theme.border
        opacity: control.enabled ? 1 : 0.45
    }
    contentItem: PlainLabel {
        text: control.displayText
        font: control.font
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        opacity: control.enabled ? 1 : 0.5
    }
    indicator: Chevron {
        x: control.width - width - 12
        y: (control.height - height) / 2
        expanded: control.popup.visible
    }
    delegate: ItemDelegate {
        required property int index
        width: control.width
        implicitHeight: 42
        highlighted: control.highlightedIndex === index
        contentItem: PlainLabel {
            text: control.textAt(index)
            color: index === control.currentIndex ? Theme.accent : Theme.text
            font.weight: index === control.currentIndex ? Font.DemiBold : Font.Normal
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        background: Rectangle { color: highlighted ? Theme.subtle : Theme.surface; radius: 4 }
    }
}
