#include "ParaViewMCPToolbar.h"

#include "ParaViewMCPPopup.h"
#include "ParaViewMCPStateAppearance.h"
#include "bridge/ParaViewMCPBridgeController.h"

#include <QIcon>
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
  this->Popup = new ParaViewMCPPopup(this);

  this->Button = new QToolButton(this);
  this->Button->setIcon(QIcon(QStringLiteral(":/ParaViewMCP/mcp-icon.png")));
  this->Button->setToolButtonStyle(Qt::ToolButtonTextUnderIcon);
  this->Button->setToolTip(QStringLiteral("ParaView MCP Server"));
  this->addWidget(this->Button);

  this->updateButtonAppearance();

  QObject::connect(this->Button,
                   &QToolButton::clicked,
                   this,
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
                   &ParaViewMCPBridgeController::serverStateChanged,
                   this,
                   [this](ParaViewMCPBridgeController::ServerState /*state*/)
                   { this->updateButtonAppearance(); });
}

void ParaViewMCPToolbar::updateButtonAppearance()
{
  const auto appearance = appearanceForState(ParaViewMCPBridgeController::instance().serverState());
  this->Button->setText(QLatin1String(appearance.Label));
  this->Button->setStyleSheet(
    QStringLiteral("QToolButton { color: %1; }").arg(QLatin1String(appearance.Color)));
}
