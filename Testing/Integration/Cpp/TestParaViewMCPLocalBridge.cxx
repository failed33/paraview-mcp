#include "FakeParaViewMCPPythonBridge.h"
#include "ParaViewMCPRequestHandler.h"
#include "ParaViewMCPSocketBridge.h"
#include "TestSocketHelpers.h"

#include <QJsonObject>
#include <QObject>
#include <QTcpSocket>
#include <QtTest>

class TestParaViewMCPLocalBridge : public QObject
{
  Q_OBJECT

private slots:
  void handlesAHelloPingAndExecuteSequence();
  void resetsHandshakeStateAcrossReconnects();
};

void TestParaViewMCPLocalBridge::handlesAHelloPingAndExecuteSequence()
{
  FakeParaViewMCPPythonBridge bridgeImpl;
  bridgeImpl.ExecutePayload = QJsonObject{
    {"ok", true},
    {"stdout", QStringLiteral("42\n")},
    {"stderr", QString()},
  };
  ParaViewMCPRequestHandler handler(bridgeImpl);
  ParaViewMCPSocketBridge bridge(bridgeImpl, handler);

  ParaViewMCPServerConfig config;
  config.Host = QStringLiteral("127.0.0.1");
  config.Port = 0;
  QString error;
  if (!bridge.start(config, &error))
  {
    QSKIP(qPrintable(error));
  }

  QTcpSocket client;
  QVERIFY(connectClientSocket(client, bridge.serverPort(), &error));

  writeJsonFrame(client,
                 QJsonObject{
                   {"request_id", QStringLiteral("hello-1")},
                   {"type", QStringLiteral("hello")},
                   {"protocol_version", ParaViewMCP::ProtocolVersion},
                   {"auth_token", QString()},
                 });

  QJsonObject response;
  QVERIFY(waitForJsonMessage(client, &response, &error));
  QCOMPARE(response.value(QStringLiteral("status")).toString(), QStringLiteral("success"));

  writeJsonFrame(client,
                 QJsonObject{
                   {"request_id", QStringLiteral("ping-1")},
                   {"type", QStringLiteral("ping")},
                   {"params", QJsonObject()},
                 });

  QVERIFY(waitForJsonMessage(client, &response, &error));
  QCOMPARE(response.value(QStringLiteral("request_id")).toString(), QStringLiteral("ping-1"));

  writeJsonFrame(client,
                 QJsonObject{
                   {"request_id", QStringLiteral("exec-1")},
                   {"type", QStringLiteral("execute_python")},
                   {"params", QJsonObject{{"code", QStringLiteral("print(42)")}}},
                 });

  QVERIFY(waitForJsonMessage(client, &response, &error));
  QCOMPARE(response.value(QStringLiteral("request_id")).toString(), QStringLiteral("exec-1"));
  QCOMPARE(
    response.value(QStringLiteral("result")).toObject().value(QStringLiteral("stdout")).toString(),
    QStringLiteral("42\n"));

  bridge.stop();
}

void TestParaViewMCPLocalBridge::resetsHandshakeStateAcrossReconnects()
{
  FakeParaViewMCPPythonBridge bridgeImpl;
  ParaViewMCPRequestHandler handler(bridgeImpl);
  ParaViewMCPSocketBridge bridge(bridgeImpl, handler);

  ParaViewMCPServerConfig config;
  config.Host = QStringLiteral("127.0.0.1");
  config.Port = 0;
  QString error;
  if (!bridge.start(config, &error))
  {
    QSKIP(qPrintable(error));
  }

  {
    QTcpSocket firstClient;
    QVERIFY(connectClientSocket(firstClient, bridge.serverPort(), &error));
    writeJsonFrame(firstClient,
                   QJsonObject{
                     {"request_id", QStringLiteral("hello-1")},
                     {"type", QStringLiteral("hello")},
                     {"protocol_version", ParaViewMCP::ProtocolVersion},
                     {"auth_token", QString()},
                   });

    QJsonObject response;
    QVERIFY(waitForJsonMessage(firstClient, &response, &error));
    QTRY_VERIFY_WITH_TIMEOUT(bridge.handshakeComplete(), 2000);
    firstClient.disconnectFromHost();
    QTRY_VERIFY_WITH_TIMEOUT(!bridge.hasClient(), 2000);
  }

  QVERIFY(!bridge.handshakeComplete());

  QTcpSocket secondClient;
  QVERIFY(connectClientSocket(secondClient, bridge.serverPort(), &error));
  writeJsonFrame(secondClient,
                 QJsonObject{
                   {"request_id", QStringLiteral("ping-1")},
                   {"type", QStringLiteral("ping")},
                   {"params", QJsonObject()},
                 });

  QJsonObject response;
  QVERIFY(waitForJsonMessage(secondClient, &response, &error));
  QCOMPARE(
    response.value(QStringLiteral("error")).toObject().value(QStringLiteral("code")).toString(),
    QStringLiteral("HANDSHAKE_REQUIRED"));

  bridge.stop();
}

QTEST_MAIN(TestParaViewMCPLocalBridge)

#include "TestParaViewMCPLocalBridge.moc"
