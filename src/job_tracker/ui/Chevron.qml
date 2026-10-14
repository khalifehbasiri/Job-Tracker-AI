import QtQuick
import "."

Item {
    property bool expanded: false
    implicitWidth: 14; implicitHeight: 10
    rotation: expanded ? 180 : 0
    Rectangle { x: 1; y: 4; width: 7; height: 1.5; rotation: 45; color: Theme.muted }
    Rectangle { x: 5; y: 4; width: 7; height: 1.5; rotation: -45; color: Theme.muted }
}
