pragma Singleton
import QtQuick

QtObject {
    property bool dark: false
    readonly property color background: dark ? "#141b18" : "#f2f4f3"
    readonly property color surface: dark ? "#1e2823" : "#ffffff"
    readonly property color sidebar: dark ? "#101713" : "#e7ede9"
    readonly property color text: dark ? "#edf3ef" : "#1c2c24"
    readonly property color muted: dark ? "#afbeb5" : "#5f7066"
    readonly property color border: dark ? "#43574b" : "#cbd6cf"
    readonly property color accent: dark ? "#9bd6b6" : "#246347"
    readonly property color accentPressed: dark ? "#7dbb98" : "#194e36"
    readonly property color accentText: dark ? "#102519" : "#ffffff"
    readonly property color selected: dark ? "#244632" : "#246347"
    readonly property color selectedText: "#ffffff"
    readonly property color warning: dark ? "#ebc68f" : "#855c23"
    readonly property color danger: dark ? "#f0a99f" : "#a64036"
    readonly property color subtle: dark ? "#2a3930" : "#e8efea"
    readonly property color hover: dark ? "#304337" : "#dce7df"
    readonly property color button: dark ? "#2a3930" : "#eaf0ec"
}
