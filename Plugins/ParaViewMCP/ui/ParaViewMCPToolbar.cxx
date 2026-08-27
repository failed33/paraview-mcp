#include "ParaViewMCPToolbar.h"

#include "ParaViewMCPPopup.h"
#include "ParaViewMCPStateAppearance.h"
#include "bridge/ParaViewMCPBridgeController.h"

#include <vtkPVVersionQuick.h>

#if PARAVIEW_VERSION_MAJOR >= 6
#include <pqCoreUtilities.h>
#else
#include <QPalette>
#endif

#include <QEvent>
#include <QHBoxLayout>
#include <QIcon>
#include <QLabel>
#include <QToolButton>

ParaViewMCPToolbar::ParaViewMCPToolbar(const QString& title, QWidget* parent)
    : QToolBar(title, parent)
{
  this->constructor();
}

ParaViewMCPToolbar::ParaViewMCPToolbar(QWidget* parent) : QToolBar(parent)
{
  this->setWindowTitle(QStringLiteral("ParaView MCP"));
  this->constructor();
}

ParaViewMCPToolbar::~ParaViewMCPToolbar() = default;

void ParaViewMCPToolbar::constructor()
{
  // Container widget: [icon button] [dot]
  this->Container = new QWidget(this);
  auto* layout = new QHBoxLayout(this->Container);
  layout->setContentsMargins(0, 0, 0, 0);
  layout->setSpacing(2);

  this->Button = new QToolButton(this->Container);
  this->Button->setToolButtonStyle(Qt::ToolButtonIconOnly);
  this->Button->setAutoRaise(true);
  layout->addWidget(this->Button);

  this->StatusDot = new QLabel(this->Container);
  this->StatusDot->setFixedSize(8, 8);
  layout->addWidget(this->StatusDot);

  this->addWidget(this->Container);

  auto* popup = new ParaViewMCPPopup(this);
  ParaViewMCPBridgeController::instance().registerPopup(popup, this->Button);

  this->updateIcon();
  this->updateButtonAppearance();

  QObject::connect(this->Button,
                   &QToolButton::clicked,
                   this,
                   []() { ParaViewMCPBridgeController::instance().togglePopup(); });

  QObject::connect(&ParaViewMCPBridgeController::instance(),
                   &ParaViewMCPBridgeController::serverStateChanged,
                   this,
                   [this](ParaViewMCPBridgeController::ServerState /*state*/)
                   { this->updateButtonAppearance(); });
}

void ParaViewMCPToolbar::changeEvent(QEvent* event)
{
  QToolBar::changeEvent(event);
  if (event->type() == QEvent::PaletteChange)
  {
    this->updateIcon();
  }
}

void ParaViewMCPToolbar::updateIcon()
{
#if PARAVIEW_VERSION_MAJOR >= 6
  const bool darkTheme = pqCoreUtilities::isDarkTheme();
#else
  const bool darkTheme = this->palette().color(QPalette::Window).lightness() < 128;
#endif
  const QString iconPath = darkTheme ? QStringLiteral(":/ParaViewMCP/mcp-icon-for-dark-theme.png")
                                     : QStringLiteral(":/ParaViewMCP/mcp-icon-for-light-theme.png");
  this->Button->setIcon(QIcon(iconPath));
}

void ParaViewMCPToolbar::updateButtonAppearance()
{
  const auto& controller = ParaViewMCPBridgeController::instance();
  const auto appearance = appearanceForState(controller.serverState());

  this->StatusDot->setStyleSheet(QStringLiteral("background-color: %1; border-radius: 4px;")
                                   .arg(QLatin1String(appearance.Color)));

  const QString statusText = QLatin1String(appearance.Label);
  if (controller.isListening())
  {
    this->Button->setToolTip(
      QStringLiteral("MCP: %1 on :%2").arg(statusText).arg(controller.port()));
  }
  else
  {
    this->Button->setToolTip(QStringLiteral("MCP: %1").arg(statusText));
  }
}
