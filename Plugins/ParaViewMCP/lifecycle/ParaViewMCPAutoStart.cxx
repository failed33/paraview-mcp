#include "ParaViewMCPAutoStart.h"

#include "bridge/ParaViewMCPBridgeController.h"

void ParaViewMCPAutoStart::startup()
{
  ParaViewMCPBridgeController::instance().initialize();
}

void ParaViewMCPAutoStart::shutdown()
{
  ParaViewMCPBridgeController::instance().shutdown();
}
