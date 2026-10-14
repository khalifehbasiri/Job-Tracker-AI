import QtQuick
import QtQuick.Controls
import "."

Label {
    color: Theme.accent
    textFormat: Text.PlainText
    font.pixelSize: 12
    font.weight: Font.DemiBold
    leftPadding: 10; rightPadding: 10
    topPadding: 5; bottomPadding: 5
    background: Rectangle {
        radius: 4
        color: Theme.subtle
    }
}
