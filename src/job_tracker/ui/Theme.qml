pragma Singleton
import QtQuick

QtObject {
    property bool dark: false
    readonly property color background: dark ? "#12201d" : "#f4f6f1"
    readonly property color surface: dark ? "#1c2e29" : "#ffffff"
    readonly property color text: dark ? "#edf3ee" : "#20362e"
    readonly property color muted: dark ? "#b1c2b9" : "#61745e"
    readonly property color border: dark ? "#3c554b" : "#dce4d7"
    readonly property color accent: dark ? "#8dd3b9" : "#216e62"
    readonly property color warning: dark ? "#e6b480" : "#965b38"
    readonly property color danger: dark ? "#f2a698" : "#b36e62"
    readonly property color subtle: dark ? "#283f35" : "#e6ede4"
    readonly property color hover: dark ? "#375447" : "#e5ece2"
    readonly property color button: dark ? "#283c32" : "#f2f5ef"
}
