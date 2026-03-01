#pragma once

#include "bridge/ParaViewMCPBridgeController.h"

struct ParaViewMCPStateAppearance
{
  const char* Label;
  const char* Color;
};

inline ParaViewMCPStateAppearance appearanceForState(ParaViewMCPBridgeController::ServerState state)
{
  switch (state)
  {
    case ParaViewMCPBridgeController::ServerState::Listening:
      return {"Listening", "#F5A623"};
    case ParaViewMCPBridgeController::ServerState::Connected:
      return {"Connected", "#4CAF50"};
    case ParaViewMCPBridgeController::ServerState::Error:
      return {"Error", "#F44336"};
    case ParaViewMCPBridgeController::ServerState::Stopped:
    default:
      return {"Stopped", "#999999"};
  }
}
