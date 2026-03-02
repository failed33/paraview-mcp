#include "FakeParaViewMCPPythonBridge.h"
#include "ParaViewMCPProtocol.h"
#include "ParaViewMCPRequestHandler.h"

#include <QJsonArray>
#include <QJsonObject>
#include <QObject>
#include <QtTest>

class TestParaViewMCPRequestHandler : public QObject
{
  Q_OBJECT

private slots:
  void handshakeSucceeds();
  void handshakeRejectsProtocolMismatch();
  void handshakeRejectsBadToken();
  void requiresHandshakeBeforeCommands();
  void pingSucceeds();
  void executePythonValidatesParams();
  void executePythonPassesThroughBridgeResults();
  void propagatesBridgeFailures();
  void handlesPipelineAndScreenshotCommands();
  void rejectsUnknownCommands();
  void getHistoryReturnsHistoryArray();
  void restoreSnapshotValidatesEntryId();
  void restoreSnapshotPassesThroughResult();
  void restoreSnapshotBridgeFailure();
  void executePythonAttachesHistoryJson();
  void inspectPipelineAttachesHistoryJson();
  void captureScreenshotAttachesHistoryJson();
};

void TestParaViewMCPRequestHandler::handshakeSucceeds()
{
  FakeParaViewMCPPythonBridge bridge;
  ParaViewMCPRequestHandler handler(bridge);

  const auto result = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("hello-1")},
      {"type", QStringLiteral("hello")},
      {"protocol_version", ParaViewMCP::ProtocolVersion},
      {"auth_token", QStringLiteral("secret")},
    },
    false,
    QStringLiteral("secret"));

  QVERIFY(result.HandshakeCompleted);
  QVERIFY(!result.CloseConnection);
  QCOMPARE(bridge.ResetCalls, 1);
  QCOMPARE(result.Response.value(QStringLiteral("status")).toString(), QStringLiteral("success"));
  const QJsonObject handshake = result.Response.value(QStringLiteral("result")).toObject();
  QCOMPARE(handshake.value(QStringLiteral("protocol_version")).toInt(),
           ParaViewMCP::ProtocolVersion);
  QVERIFY(handshake.value(QStringLiteral("python_ready")).toBool());
}

void TestParaViewMCPRequestHandler::handshakeRejectsProtocolMismatch()
{
  FakeParaViewMCPPythonBridge bridge;
  ParaViewMCPRequestHandler handler(bridge);

  const auto result = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("hello-1")},
      {"type", QStringLiteral("hello")},
      {"protocol_version", 999},
      {"auth_token", QStringLiteral("secret")},
    },
    false,
    QStringLiteral("secret"));

  QVERIFY(result.CloseConnection);
  QVERIFY(result.ResetSession);
  QCOMPARE(result.Response.value(QStringLiteral("error"))
             .toObject()
             .value(QStringLiteral("code"))
             .toString(),
           QStringLiteral("PROTOCOL_MISMATCH"));
}

void TestParaViewMCPRequestHandler::handshakeRejectsBadToken()
{
  FakeParaViewMCPPythonBridge bridge;
  ParaViewMCPRequestHandler handler(bridge);

  const auto result = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("hello-1")},
      {"type", QStringLiteral("hello")},
      {"protocol_version", ParaViewMCP::ProtocolVersion},
      {"auth_token", QStringLiteral("wrong")},
    },
    false,
    QStringLiteral("secret"));

  QVERIFY(result.CloseConnection);
  QCOMPARE(result.Response.value(QStringLiteral("error"))
             .toObject()
             .value(QStringLiteral("code"))
             .toString(),
           QStringLiteral("AUTH_FAILED"));
}

void TestParaViewMCPRequestHandler::requiresHandshakeBeforeCommands()
{
  FakeParaViewMCPPythonBridge bridge;
  ParaViewMCPRequestHandler handler(bridge);

  const auto result = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("ping-1")},
      {"type", QStringLiteral("ping")},
      {"params", QJsonObject()},
    },
    false,
    QString());

  QVERIFY(result.CloseConnection);
  QCOMPARE(result.Response.value(QStringLiteral("error"))
             .toObject()
             .value(QStringLiteral("code"))
             .toString(),
           QStringLiteral("HANDSHAKE_REQUIRED"));
}

void TestParaViewMCPRequestHandler::pingSucceeds()
{
  FakeParaViewMCPPythonBridge bridge;
  ParaViewMCPRequestHandler handler(bridge);

  const auto result = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("ping-1")},
      {"type", QStringLiteral("ping")},
      {"params", QJsonObject()},
    },
    true,
    QString());

  QCOMPARE(result.Response.value(QStringLiteral("request_id")).toString(),
           QStringLiteral("ping-1"));
  QCOMPARE(result.Response.value(QStringLiteral("status")).toString(), QStringLiteral("success"));
}

void TestParaViewMCPRequestHandler::executePythonValidatesParams()
{
  FakeParaViewMCPPythonBridge bridge;
  ParaViewMCPRequestHandler handler(bridge);

  const auto result = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("exec-1")},
      {"type", QStringLiteral("execute_python")},
      {"params", QJsonObject()},
    },
    true,
    QString());

  QCOMPARE(result.Response.value(QStringLiteral("error"))
             .toObject()
             .value(QStringLiteral("code"))
             .toString(),
           QStringLiteral("INVALID_PARAMS"));
}

void TestParaViewMCPRequestHandler::executePythonPassesThroughBridgeResults()
{
  FakeParaViewMCPPythonBridge bridge;
  bridge.ExecutePayload = QJsonObject{
    {"ok", true},
    {"stdout", QStringLiteral("42\n")},
  };
  ParaViewMCPRequestHandler handler(bridge);

  const auto result = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("exec-1")},
      {"type", QStringLiteral("execute_python")},
      {"params", QJsonObject{{"code", QStringLiteral("print(42)")}}},
    },
    true,
    QString());

  QCOMPARE(bridge.ExecuteCalls, 1);
  QCOMPARE(bridge.LastCode, QStringLiteral("print(42)"));
  QCOMPARE(result.Response.value(QStringLiteral("status")).toString(), QStringLiteral("success"));
  QCOMPARE(result.Response.value(QStringLiteral("result"))
             .toObject()
             .value(QStringLiteral("stdout"))
             .toString(),
           QStringLiteral("42\n"));
}

void TestParaViewMCPRequestHandler::propagatesBridgeFailures()
{
  FakeParaViewMCPPythonBridge bridge;
  bridge.ExecuteResult = false;
  bridge.ExecuteError = QStringLiteral("exec failed");
  ParaViewMCPRequestHandler handler(bridge);

  const auto result = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("exec-1")},
      {"type", QStringLiteral("execute_python")},
      {"params", QJsonObject{{"code", QStringLiteral("print(42)")}}},
    },
    true,
    QString());

  QCOMPARE(result.Response.value(QStringLiteral("error"))
             .toObject()
             .value(QStringLiteral("code"))
             .toString(),
           QStringLiteral("PYTHON_BRIDGE_ERROR"));
  QCOMPARE(result.Response.value(QStringLiteral("error"))
             .toObject()
             .value(QStringLiteral("message"))
             .toString(),
           QStringLiteral("exec failed"));
}

void TestParaViewMCPRequestHandler::handlesPipelineAndScreenshotCommands()
{
  FakeParaViewMCPPythonBridge bridge;
  bridge.InspectPayload = QJsonObject{{"count", 2}};
  bridge.ScreenshotPayload = QJsonObject{
    {"format", QStringLiteral("png")},
    {"image_data", QStringLiteral("ZmFrZQ==")},
  };
  ParaViewMCPRequestHandler handler(bridge);

  const auto inspectResult = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("inspect-1")},
      {"type", QStringLiteral("inspect_pipeline")},
      {"params", QJsonObject()},
    },
    true,
    QString());
  QCOMPARE(inspectResult.Response.value(QStringLiteral("result"))
             .toObject()
             .value(QStringLiteral("count"))
             .toInt(),
           2);

  const auto screenshotResult = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("shot-1")},
      {"type", QStringLiteral("capture_screenshot")},
      {"params", QJsonObject{{"width", 640}, {"height", 480}}},
    },
    true,
    QString());
  QCOMPARE(bridge.ScreenshotCalls, 1);
  QCOMPARE(bridge.LastWidth, 640);
  QCOMPARE(bridge.LastHeight, 480);
  QCOMPARE(screenshotResult.Response.value(QStringLiteral("result"))
             .toObject()
             .value(QStringLiteral("format"))
             .toString(),
           QStringLiteral("png"));
}

void TestParaViewMCPRequestHandler::rejectsUnknownCommands()
{
  FakeParaViewMCPPythonBridge bridge;
  ParaViewMCPRequestHandler handler(bridge);

  const auto result = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("unknown-1")},
      {"type", QStringLiteral("does_not_exist")},
      {"params", QJsonObject()},
    },
    true,
    QString());

  QCOMPARE(result.Response.value(QStringLiteral("error"))
             .toObject()
             .value(QStringLiteral("code"))
             .toString(),
           QStringLiteral("UNKNOWN_COMMAND"));
}

void TestParaViewMCPRequestHandler::getHistoryReturnsHistoryArray()
{
  FakeParaViewMCPPythonBridge bridge;
  bridge.HistoryPayload = QJsonArray{
    QJsonObject{{"id", 1}, {"command", QStringLiteral("execute_python")}},
    QJsonObject{{"id", 2}, {"command", QStringLiteral("inspect_pipeline")}},
  };
  ParaViewMCPRequestHandler handler(bridge);

  const auto result = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("hist-1")},
      {"type", QStringLiteral("get_history")},
      {"params", QJsonObject()},
    },
    true,
    QString());

  QCOMPARE(result.Response.value(QStringLiteral("status")).toString(), QStringLiteral("success"));
  const QJsonArray history = result.Response.value(QStringLiteral("result"))
                               .toObject()
                               .value(QStringLiteral("history"))
                               .toArray();
  QCOMPARE(history.size(), 2);
  QCOMPARE(history[0].toObject().value(QStringLiteral("id")).toInt(), 1);
  QCOMPARE(history[1].toObject().value(QStringLiteral("id")).toInt(), 2);
  QVERIFY(!result.HistoryJson.isEmpty());
}

void TestParaViewMCPRequestHandler::restoreSnapshotValidatesEntryId()
{
  FakeParaViewMCPPythonBridge bridge;
  ParaViewMCPRequestHandler handler(bridge);

  // Missing entry_id
  auto result = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("restore-1")},
      {"type", QStringLiteral("restore_snapshot")},
      {"params", QJsonObject()},
    },
    true,
    QString());

  QCOMPARE(result.Response.value(QStringLiteral("error"))
             .toObject()
             .value(QStringLiteral("code"))
             .toString(),
           QStringLiteral("INVALID_PARAMS"));

  // Zero entry_id
  result = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("restore-2")},
      {"type", QStringLiteral("restore_snapshot")},
      {"params", QJsonObject{{"entry_id", 0}}},
    },
    true,
    QString());

  QCOMPARE(result.Response.value(QStringLiteral("error"))
             .toObject()
             .value(QStringLiteral("code"))
             .toString(),
           QStringLiteral("INVALID_PARAMS"));

  // Negative entry_id
  result = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("restore-3")},
      {"type", QStringLiteral("restore_snapshot")},
      {"params", QJsonObject{{"entry_id", -5}}},
    },
    true,
    QString());

  QCOMPARE(result.Response.value(QStringLiteral("error"))
             .toObject()
             .value(QStringLiteral("code"))
             .toString(),
           QStringLiteral("INVALID_PARAMS"));
}

void TestParaViewMCPRequestHandler::restoreSnapshotPassesThroughResult()
{
  FakeParaViewMCPPythonBridge bridge;
  ParaViewMCPRequestHandler handler(bridge);

  const auto result = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("restore-1")},
      {"type", QStringLiteral("restore_snapshot")},
      {"params", QJsonObject{{"entry_id", 3}}},
    },
    true,
    QString());

  QCOMPARE(bridge.LastRestoreEntryId, 3);
  QCOMPARE(result.Response.value(QStringLiteral("status")).toString(), QStringLiteral("success"));
  QVERIFY(result.Response.value(QStringLiteral("result"))
            .toObject()
            .value(QStringLiteral("ok"))
            .toBool());
  QVERIFY(!result.HistoryJson.isEmpty());
}

void TestParaViewMCPRequestHandler::restoreSnapshotBridgeFailure()
{
  FakeParaViewMCPPythonBridge bridge;
  bridge.RestoreResult = false;
  bridge.RestoreError = QStringLiteral("snapshot not found");
  ParaViewMCPRequestHandler handler(bridge);

  const auto result = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("restore-1")},
      {"type", QStringLiteral("restore_snapshot")},
      {"params", QJsonObject{{"entry_id", 1}}},
    },
    true,
    QString());

  QCOMPARE(result.Response.value(QStringLiteral("error"))
             .toObject()
             .value(QStringLiteral("code"))
             .toString(),
           QStringLiteral("RESTORE_ERROR"));
  QCOMPARE(result.Response.value(QStringLiteral("error"))
             .toObject()
             .value(QStringLiteral("message"))
             .toString(),
           QStringLiteral("snapshot not found"));
}

void TestParaViewMCPRequestHandler::executePythonAttachesHistoryJson()
{
  FakeParaViewMCPPythonBridge bridge;
  bridge.HistoryPayload = QJsonArray{QJsonObject{{"id", 1}}};
  ParaViewMCPRequestHandler handler(bridge);

  const auto result = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("exec-1")},
      {"type", QStringLiteral("execute_python")},
      {"params", QJsonObject{{"code", QStringLiteral("x = 1")}}},
    },
    true,
    QString());

  QCOMPARE(result.Response.value(QStringLiteral("status")).toString(), QStringLiteral("success"));
  QVERIFY(!result.HistoryJson.isEmpty());
  QVERIFY(result.HistoryJson.contains(QStringLiteral("\"id\":1")));
}

void TestParaViewMCPRequestHandler::inspectPipelineAttachesHistoryJson()
{
  FakeParaViewMCPPythonBridge bridge;
  bridge.HistoryPayload = QJsonArray{QJsonObject{{"id", 1}}};
  ParaViewMCPRequestHandler handler(bridge);

  const auto result = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("inspect-1")},
      {"type", QStringLiteral("inspect_pipeline")},
      {"params", QJsonObject()},
    },
    true,
    QString());

  QCOMPARE(result.Response.value(QStringLiteral("status")).toString(), QStringLiteral("success"));
  QVERIFY(!result.HistoryJson.isEmpty());
}

void TestParaViewMCPRequestHandler::captureScreenshotAttachesHistoryJson()
{
  FakeParaViewMCPPythonBridge bridge;
  bridge.HistoryPayload = QJsonArray{QJsonObject{{"id", 1}}};
  ParaViewMCPRequestHandler handler(bridge);

  const auto result = handler.handleMessage(
    QJsonObject{
      {"request_id", QStringLiteral("shot-1")},
      {"type", QStringLiteral("capture_screenshot")},
      {"params", QJsonObject{{"width", 800}, {"height", 600}}},
    },
    true,
    QString());

  QCOMPARE(result.Response.value(QStringLiteral("status")).toString(), QStringLiteral("success"));
  QVERIFY(!result.HistoryJson.isEmpty());
}

QTEST_APPLESS_MAIN(TestParaViewMCPRequestHandler)

#include "TestParaViewMCPRequestHandler.moc"
