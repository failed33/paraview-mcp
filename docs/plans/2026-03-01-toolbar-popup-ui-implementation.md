# Toolbar Popup UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the ParaView MCP dock panel with a toolbar button (icon + colored status label) that opens a popup for server configuration and log viewing.

**Architecture:** The dock widget is removed entirely. A `QToolBar` subclass provides a `QToolButton` with the MCP icon and a colored status label. Clicking the button opens a `QFrame` popup (`Qt::Popup`) containing the same form fields, start/stop buttons, and a collapsible log. The `BridgeController` gains a `ServerState` enum that both toolbar and popup observe.

**Tech Stack:** C++ / Qt5+Qt6 / ParaView plugin API / CMake

**Design doc:** `docs/plans/2026-03-01-toolbar-popup-ui-design.md`

---

### Task 1: Add ServerState enum and signal to BridgeController

**Files:**
- Modify: `Plugins/ParaViewMCP/bridge/ParaViewMCPBridgeController.h`
- Modify: `Plugins/ParaViewMCP/bridge/ParaViewMCPBridgeController.cxx`

**Step 1: Add ServerState enum and new members to header**

In `ParaViewMCPBridgeController.h`, add the enum and new signal/method. Remove dock-specific forward declaration and members.

```cpp
// At top of class, before Q_OBJECT:
// Remove: class ParaViewMCPDockWindow;

// Add forward declaration:
class ParaViewMCPPopup;

// Add public enum inside the class body, after Q_OBJECT:
public:
  enum class ServerState
  {
    Stopped,
    Listening,
    Connected,
    Error
  };
  Q_ENUM(ServerState)

// Replace these methods:
//   void registerDockWindow(ParaViewMCPDockWindow* dockWindow);
//   void showDockWindow();
// With:
  void registerPopup(ParaViewMCPPopup* popup);
  void showPopup(QWidget* anchor = nullptr);

// Add new public method:
  ServerState serverState() const;

// Add new signal (in signals: section):
  void serverStateChanged(ServerState state);

// Replace private member:
//   QPointer<ParaViewMCPDockWindow> DockWindow;
// With:
  QPointer<ParaViewMCPPopup> Popup;

// Add private member:
  ServerState CurrentState = ServerState::Stopped;

// Add private method:
  void updateServerState();
```

**Step 2: Implement the new methods in .cxx**

In `ParaViewMCPBridgeController.cxx`:

Replace `#include "ParaViewMCPDockWindow.h"` with `#include "ParaViewMCPPopup.h"`.

Replace `registerDockWindow` and `showDockWindow`:

```cpp
void ParaViewMCPBridgeController::registerPopup(ParaViewMCPPopup* popup)
{
  this->Popup = popup;
}

void ParaViewMCPBridgeController::showPopup(QWidget* anchor)
{
  if (!this->Popup)
  {
    return;
  }

  this->Popup->showRelativeTo(anchor);
}
```

Add `serverState()`:

```cpp
ParaViewMCPBridgeController::ServerState ParaViewMCPBridgeController::serverState() const
{
  return this->CurrentState;
}
```

Add `updateServerState()` — derives state from socket bridge:

```cpp
void ParaViewMCPBridgeController::updateServerState()
{
  ServerState newState = ServerState::Stopped;

  if (this->SocketBridge.hasClient())
  {
    newState = ServerState::Connected;
  }
  else if (this->SocketBridge.isListening())
  {
    newState = ServerState::Listening;
  }

  if (newState != this->CurrentState)
  {
    this->CurrentState = newState;
    emit this->serverStateChanged(newState);
  }
}
```

Update `setStatus()` to also call `updateServerState()`:

```cpp
void ParaViewMCPBridgeController::setStatus(const QString& status)
{
  if (status == QStringLiteral("Error"))
  {
    if (this->CurrentState != ServerState::Error)
    {
      this->CurrentState = ServerState::Error;
      emit this->serverStateChanged(ServerState::Error);
    }
  }
  else
  {
    this->updateServerState();
  }

  this->LastStatus = status;
  emit this->statusChanged(status);
}
```

Update `initialize()` to emit initial state:

```cpp
void ParaViewMCPBridgeController::initialize()
{
  if (this->Initialized)
  {
    return;
  }

  this->Initialized = true;
  this->Config = ParaViewMCPServerConfig::load();
  this->setStatus(QStringLiteral("Stopped"));
}
```

**Step 3: Verify it compiles**

Run: `cd <build-dir> && cmake --build . --target ParaViewMCPBridgeCore 2>&1 | head -30`

This will fail because `ParaViewMCPPopup.h` doesn't exist yet and the dock window references are gone from CMake. That's expected — we'll fix it in Task 3.

**Step 4: Commit**

```bash
git add Plugins/ParaViewMCP/bridge/ParaViewMCPBridgeController.h \
        Plugins/ParaViewMCP/bridge/ParaViewMCPBridgeController.cxx
git commit -m "refactor(controller): replace dock API with popup API and ServerState enum"
```

---

### Task 2: Create ParaViewMCPPopup widget

**Files:**
- Create: `Plugins/ParaViewMCP/ui/ParaViewMCPPopup.h`
- Create: `Plugins/ParaViewMCP/ui/ParaViewMCPPopup.cxx`

**Step 1: Write the popup header**

```cpp
#pragma once

#include <QFrame>

class QLabel;
class QLineEdit;
class QPlainTextEdit;
class QPushButton;
class QSpinBox;
class QToolButton;

class ParaViewMCPPopup : public QFrame
{
  Q_OBJECT

public:
  explicit ParaViewMCPPopup(QWidget* parent = nullptr);

  void showRelativeTo(QWidget* anchor);
  void refreshFromController();

private:
  void syncState();

  QLabel* StatusDot = nullptr;
  QLabel* StatusText = nullptr;
  QLineEdit* HostField = nullptr;
  QSpinBox* PortField = nullptr;
  QLineEdit* TokenField = nullptr;
  QPushButton* StartButton = nullptr;
  QPushButton* StopButton = nullptr;
  QToolButton* LogToggle = nullptr;
  QPlainTextEdit* LogOutput = nullptr;
};
```

**Step 2: Write the popup implementation**

```cpp
#include "ParaViewMCPPopup.h"

#include "bridge/ParaViewMCPBridgeController.h"

#include <QFormLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QScreen>
#include <QSpinBox>
#include <QToolButton>
#include <QVBoxLayout>

namespace
{
constexpr int PopupWidth = 320;

struct StateAppearance
{
  const char* Label;
  const char* Color;
};

StateAppearance appearanceForState(ParaViewMCPBridgeController::ServerState state)
{
  switch (state)
  {
    case ParaViewMCPBridgeController::ServerState::Listening:
      return { "Listening", "#F5A623" };
    case ParaViewMCPBridgeController::ServerState::Connected:
      return { "Connected", "#4CAF50" };
    case ParaViewMCPBridgeController::ServerState::Error:
      return { "Error", "#F44336" };
    case ParaViewMCPBridgeController::ServerState::Stopped:
    default:
      return { "Stopped", "#999999" };
  }
}
} // namespace

ParaViewMCPPopup::ParaViewMCPPopup(QWidget* parent)
    : QFrame(parent, Qt::Popup | Qt::FramelessWindowHint)
{
  this->setFixedWidth(PopupWidth);
  this->setFrameShape(QFrame::StyledPanel);
  this->setFrameShadow(QFrame::Raised);

  auto* layout = new QVBoxLayout(this);
  layout->setContentsMargins(12, 12, 12, 12);
  layout->setSpacing(8);

  // --- Status row ---
  auto* statusRow = new QHBoxLayout();
  this->StatusDot = new QLabel(this);
  this->StatusDot->setFixedSize(10, 10);
  this->StatusText = new QLabel(QStringLiteral("Stopped"), this);
  auto font = this->StatusText->font();
  font.setBold(true);
  this->StatusText->setFont(font);
  statusRow->addWidget(this->StatusDot);
  statusRow->addWidget(this->StatusText);
  statusRow->addStretch();
  layout->addLayout(statusRow);

  // --- Form fields ---
  auto* formLayout = new QFormLayout();
  formLayout->setFieldGrowthPolicy(QFormLayout::ExpandingFieldsGrow);

  this->HostField = new QLineEdit(this);
  this->PortField = new QSpinBox(this);
  this->PortField->setRange(1, 65535);
  this->TokenField = new QLineEdit(this);
  this->TokenField->setEchoMode(QLineEdit::Password);

  formLayout->addRow(QStringLiteral("Host"), this->HostField);
  formLayout->addRow(QStringLiteral("Port"), this->PortField);
  formLayout->addRow(QStringLiteral("Token"), this->TokenField);
  layout->addLayout(formLayout);

  // --- Buttons ---
  auto* buttonLayout = new QHBoxLayout();
  this->StartButton = new QPushButton(QStringLiteral("Start Server"), this);
  this->StopButton = new QPushButton(QStringLiteral("Stop Server"), this);
  buttonLayout->addWidget(this->StartButton);
  buttonLayout->addWidget(this->StopButton);
  layout->addLayout(buttonLayout);

  // --- Collapsible log ---
  this->LogToggle = new QToolButton(this);
  this->LogToggle->setArrowType(Qt::RightArrow);
  this->LogToggle->setText(QStringLiteral(" Log"));
  this->LogToggle->setToolButtonStyle(Qt::ToolButtonTextBesideIcon);
  this->LogToggle->setAutoRaise(true);
  this->LogToggle->setCheckable(true);
  layout->addWidget(this->LogToggle);

  this->LogOutput = new QPlainTextEdit(this);
  this->LogOutput->setReadOnly(true);
  this->LogOutput->setMaximumBlockCount(200);
  this->LogOutput->setFixedHeight(140);
  this->LogOutput->setVisible(false);
  layout->addWidget(this->LogOutput);

  // --- Connections ---
  ParaViewMCPBridgeController& controller = ParaViewMCPBridgeController::instance();
  controller.registerPopup(this);

  QObject::connect(this->StartButton, &QPushButton::clicked, this,
    [this]()
    {
      ParaViewMCPBridgeController::instance().startServer(
        this->HostField->text(),
        static_cast<quint16>(this->PortField->value()),
        this->TokenField->text());
      this->syncState();
    });

  QObject::connect(this->StopButton, &QPushButton::clicked, this,
    [this]()
    {
      ParaViewMCPBridgeController::instance().stopServer();
      this->syncState();
    });

  QObject::connect(&controller, &ParaViewMCPBridgeController::statusChanged, this,
    [this](const QString& /*status*/) { this->syncState(); });

  QObject::connect(&controller, &ParaViewMCPBridgeController::serverStateChanged, this,
    [this](ParaViewMCPBridgeController::ServerState state)
    {
      const auto appearance = appearanceForState(state);
      this->StatusDot->setStyleSheet(
        QStringLiteral("background-color: %1; border-radius: 5px;")
          .arg(QLatin1String(appearance.Color)));
      this->StatusText->setText(QLatin1String(appearance.Label));
      this->StatusText->setStyleSheet(
        QStringLiteral("color: %1;").arg(QLatin1String(appearance.Color)));
    });

  QObject::connect(&controller, &ParaViewMCPBridgeController::logChanged, this,
    [this](const QString& message) { this->LogOutput->setPlainText(message); });

  QObject::connect(this->LogToggle, &QToolButton::toggled, this,
    [this](bool checked)
    {
      this->LogToggle->setArrowType(checked ? Qt::DownArrow : Qt::RightArrow);
      this->LogOutput->setVisible(checked);
      // Resize popup to fit new content
      this->adjustSize();
    });

  this->refreshFromController();
}

void ParaViewMCPPopup::showRelativeTo(QWidget* anchor)
{
  this->refreshFromController();

  if (anchor != nullptr)
  {
    QPoint pos = anchor->mapToGlobal(QPoint(0, anchor->height()));
    QScreen* screen = anchor->screen();
    if (screen != nullptr)
    {
      const QRect available = screen->availableGeometry();
      if (pos.x() + this->width() > available.right())
      {
        pos.setX(available.right() - this->width());
      }
      if (pos.y() + this->sizeHint().height() > available.bottom())
      {
        pos.setY(anchor->mapToGlobal(QPoint(0, 0)).y() - this->sizeHint().height());
      }
    }
    this->move(pos);
  }

  this->show();
}

void ParaViewMCPPopup::refreshFromController()
{
  const ParaViewMCPBridgeController& controller = ParaViewMCPBridgeController::instance();
  this->HostField->setText(controller.host());
  this->PortField->setValue(static_cast<int>(controller.port()));
  this->LogOutput->setPlainText(controller.lastLog());

  const auto appearance = appearanceForState(controller.serverState());
  this->StatusDot->setStyleSheet(
    QStringLiteral("background-color: %1; border-radius: 5px;")
      .arg(QLatin1String(appearance.Color)));
  this->StatusText->setText(QLatin1String(appearance.Label));
  this->StatusText->setStyleSheet(
    QStringLiteral("color: %1;").arg(QLatin1String(appearance.Color)));

  this->syncState();
}

void ParaViewMCPPopup::syncState()
{
  const ParaViewMCPBridgeController& controller = ParaViewMCPBridgeController::instance();
  const bool listening = controller.isListening();

  this->HostField->setEnabled(!listening);
  this->PortField->setEnabled(!listening);
  this->TokenField->setEnabled(!listening);
  this->StartButton->setEnabled(!listening);
  this->StopButton->setEnabled(listening);
}
```

**Step 3: Commit**

```bash
git add Plugins/ParaViewMCP/ui/ParaViewMCPPopup.h \
        Plugins/ParaViewMCP/ui/ParaViewMCPPopup.cxx
git commit -m "feat(ui): add ParaViewMCPPopup widget with collapsible log"
```

---

### Task 3: Create ParaViewMCPToolbar widget

**Files:**
- Create: `Plugins/ParaViewMCP/ui/ParaViewMCPToolbar.h`
- Create: `Plugins/ParaViewMCP/ui/ParaViewMCPToolbar.cxx`

**Step 1: Write the toolbar header**

```cpp
#pragma once

#include <QToolBar>

class ParaViewMCPPopup;
class QToolButton;

class ParaViewMCPToolbar : public QToolBar
{
  Q_OBJECT

public:
  ParaViewMCPToolbar(const QString& title, QWidget* parent = nullptr);
  ParaViewMCPToolbar(QWidget* parent = nullptr);
  ~ParaViewMCPToolbar() override;

private:
  void constructor();
  void updateButtonAppearance();

  QToolButton* Button = nullptr;
  ParaViewMCPPopup* Popup = nullptr;
};
```

**Step 2: Write the toolbar implementation**

```cpp
#include "ParaViewMCPToolbar.h"

#include "ParaViewMCPPopup.h"
#include "bridge/ParaViewMCPBridgeController.h"

#include <QIcon>
#include <QToolButton>

namespace
{
struct StateAppearance
{
  const char* Label;
  const char* Color;
};

StateAppearance appearanceForState(ParaViewMCPBridgeController::ServerState state)
{
  switch (state)
  {
    case ParaViewMCPBridgeController::ServerState::Listening:
      return { "Listening", "#F5A623" };
    case ParaViewMCPBridgeController::ServerState::Connected:
      return { "Connected", "#4CAF50" };
    case ParaViewMCPBridgeController::ServerState::Error:
      return { "Error", "#F44336" };
    case ParaViewMCPBridgeController::ServerState::Stopped:
    default:
      return { "Stopped", "#999999" };
  }
}
} // namespace

ParaViewMCPToolbar::ParaViewMCPToolbar(const QString& title, QWidget* parent)
    : QToolBar(title, parent)
{
  this->constructor();
}

ParaViewMCPToolbar::ParaViewMCPToolbar(QWidget* parent)
    : QToolBar(parent)
{
  this->setWindowTitle(QStringLiteral("ParaView MCP"));
  this->constructor();
}

ParaViewMCPToolbar::~ParaViewMCPToolbar() = default;

void ParaViewMCPToolbar::constructor()
{
  this->Popup = new ParaViewMCPPopup(this);

  this->Button = new QToolButton(this);
  this->Button->setIcon(QIcon(QStringLiteral(":/ParaViewMCP/mcp-icon.png")));
  this->Button->setToolButtonStyle(Qt::ToolButtonTextUnderIcon);
  this->Button->setToolTip(QStringLiteral("ParaView MCP Server"));
  this->addWidget(this->Button);

  this->updateButtonAppearance();

  QObject::connect(this->Button, &QToolButton::clicked, this,
    [this]()
    {
      if (this->Popup->isVisible())
      {
        this->Popup->hide();
      }
      else
      {
        this->Popup->showRelativeTo(this->Button);
      }
    });

  QObject::connect(&ParaViewMCPBridgeController::instance(),
    &ParaViewMCPBridgeController::serverStateChanged, this,
    [this](ParaViewMCPBridgeController::ServerState /*state*/)
    { this->updateButtonAppearance(); });
}

void ParaViewMCPToolbar::updateButtonAppearance()
{
  const auto appearance =
    appearanceForState(ParaViewMCPBridgeController::instance().serverState());
  this->Button->setText(QLatin1String(appearance.Label));
  this->Button->setStyleSheet(
    QStringLiteral("QToolButton { color: %1; }").arg(QLatin1String(appearance.Color)));
}
```

**Step 3: Commit**

```bash
git add Plugins/ParaViewMCP/ui/ParaViewMCPToolbar.h \
        Plugins/ParaViewMCP/ui/ParaViewMCPToolbar.cxx
git commit -m "feat(ui): add ParaViewMCPToolbar with status-colored button"
```

---

### Task 4: Update ActionGroup to use popup instead of dock

**Files:**
- Modify: `Plugins/ParaViewMCP/ui/ParaViewMCPActionGroup.cxx`

**Step 1: Change showDockWindow() to showPopup()**

Replace the entire lambda in the connect call:

```cpp
// Old:
QObject::connect(action,
                 &QAction::triggered,
                 []() { ParaViewMCPBridgeController::instance().showDockWindow(); });

// New:
QObject::connect(action,
                 &QAction::triggered,
                 []() { ParaViewMCPBridgeController::instance().showPopup(); });
```

**Step 2: Commit**

```bash
git add Plugins/ParaViewMCP/ui/ParaViewMCPActionGroup.cxx
git commit -m "refactor(ui): action group opens popup instead of dock window"
```

---

### Task 5: Update CMakeLists.txt — replace dock with toolbar

**Files:**
- Modify: `Plugins/ParaViewMCP/CMakeLists.txt`

**Step 1: Update source lists**

In `paraview_mcp_plugin_sources`, replace dock window files with new files:

```cmake
# Remove these two lines:
#   ui/ParaViewMCPDockWindow.cxx
#   ui/ParaViewMCPDockWindow.h
# Add these four lines:
  ui/ParaViewMCPPopup.cxx
  ui/ParaViewMCPPopup.h
  ui/ParaViewMCPToolbar.cxx
  ui/ParaViewMCPToolbar.h
```

In `paraview_mcp_lint_sources`, replace:

```cmake
# Remove:
#   ui/ParaViewMCPDockWindow.cxx
# Add:
  ui/ParaViewMCPPopup.cxx
  ui/ParaViewMCPToolbar.cxx
```

**Step 2: Replace dock_window macro with toolbar macro**

Remove the `paraview_plugin_add_dock_window` block:

```cmake
# Remove this entire block:
# paraview_plugin_add_dock_window(
#   CLASS_NAME ParaViewMCPDockWindow
#   DOCK_AREA Right
#   INTERFACES paraview_mcp_dock_interfaces
#   SOURCES paraview_mcp_dock_wrapper_sources
# )
# list(APPEND paraview_mcp_ui_interfaces ${paraview_mcp_dock_interfaces})
# list(APPEND paraview_mcp_ui_sources ${paraview_mcp_dock_wrapper_sources})
```

Add the toolbar macro in its place:

```cmake
paraview_plugin_add_toolbar(
  CLASS_NAME ParaViewMCPToolbar
  INTERFACES paraview_mcp_toolbar_interfaces
  SOURCES paraview_mcp_toolbar_wrapper_sources
)
list(APPEND paraview_mcp_ui_interfaces ${paraview_mcp_toolbar_interfaces})
list(APPEND paraview_mcp_ui_sources ${paraview_mcp_toolbar_wrapper_sources})
```

**Step 3: Commit**

```bash
git add Plugins/ParaViewMCP/CMakeLists.txt
git commit -m "build: replace dock window with toolbar in CMake config"
```

---

### Task 6: Delete old dock window files

**Files:**
- Delete: `Plugins/ParaViewMCP/ui/ParaViewMCPDockWindow.h`
- Delete: `Plugins/ParaViewMCP/ui/ParaViewMCPDockWindow.cxx`

**Step 1: Remove the files**

```bash
git rm Plugins/ParaViewMCP/ui/ParaViewMCPDockWindow.h \
       Plugins/ParaViewMCP/ui/ParaViewMCPDockWindow.cxx
```

**Step 2: Commit**

```bash
git commit -m "refactor(ui): remove old dock window files"
```

---

### Task 7: Build and verify

**Step 1: Configure and build**

```bash
cd <build-dir>
cmake --build . --target ParaViewMCP 2>&1
```

Expected: clean build with no errors.

**Step 2: Fix any compilation issues**

If there are include path issues or missing symbols, fix them. Common issues:
- The generated toolbar wrapper may need the `ui/` include directory (already in `target_include_directories`).
- `Q_ENUM(ServerState)` requires `ServerState` to be defined before the `Q_OBJECT` macro expansion — verify ordering.

**Step 3: Commit any fixes**

```bash
git add -u
git commit -m "fix: resolve build issues from toolbar refactor"
```

---

### Task 8: Manual smoke test in ParaView

**Step 1: Launch ParaView with the plugin**

Open ParaView, verify:
- [ ] MCP toolbar appears with icon and "Stopped" label in gray
- [ ] Clicking the toolbar button opens the popup below it
- [ ] Clicking outside the popup dismisses it
- [ ] `Tools > ParaView MCP` menu also opens the popup
- [ ] Host/Port/Token fields are editable when stopped
- [ ] Clicking "Start Server" changes toolbar label to "Listening" in amber
- [ ] Fields become disabled while listening
- [ ] Clicking "Stop Server" returns to "Stopped" in gray
- [ ] Log disclosure triangle toggles the log panel visibility
- [ ] Popup resizes when log is toggled
- [ ] Connecting a client changes toolbar label to "Connected" in green
- [ ] Using an in-use port shows "Error" in red

**Step 2: Commit final state**

```bash
git add -u
git commit -m "feat(ui): complete toolbar popup UI replacing dock panel"
```

---

### Summary of commit sequence

1. `refactor(controller): replace dock API with popup API and ServerState enum`
2. `feat(ui): add ParaViewMCPPopup widget with collapsible log`
3. `feat(ui): add ParaViewMCPToolbar with status-colored button`
4. `refactor(ui): action group opens popup instead of dock window`
5. `build: replace dock window with toolbar in CMake config`
6. `refactor(ui): remove old dock window files`
7. `fix: resolve build issues from toolbar refactor` (if needed)
8. `feat(ui): complete toolbar popup UI replacing dock panel` (if needed)
