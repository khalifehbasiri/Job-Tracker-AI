import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Card {
    property string label
    property string value
    property string accent: "#216e62"
    implicitHeight: 125
    ColumnLayout {
        anchors.fill: parent
        Label { text: label; color: "#758079"; font.pixelSize: 13 }
        Label { text: value; color: accent; font.pixelSize: 36; font.weight: Font.DemiBold }
    }
}
