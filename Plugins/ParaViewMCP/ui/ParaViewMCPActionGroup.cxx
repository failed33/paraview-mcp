#include "ParaViewMCPActionGroup.h"

#include "bridge/ParaViewMCPBridgeController.h"

#include <pqCoreUtilities.h>

#include <QAction>
#include <QCursor>
#include <QIcon>

ParaViewMCPActionGroup::ParaViewMCPActionGroup(QObject* parent) : QActionGroup(parent)
{
  auto* action = new QAction(
    QIcon(QStringLiteral(":/ParaViewMCP/mcp-icon.png")), QStringLiteral("ParaView MCP"), this);
  this->addAction(action);
  QObject::connect(action,
                   &QAction::triggered,
                   []()
                   {
                     QWidget* mainWindow = pqCoreUtilities::mainWidget();
                     ParaViewMCPBridgeController::instance().showPopup(mainWindow);
                   });
}
