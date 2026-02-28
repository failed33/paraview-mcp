#include "ParaViewMCPServerConfig.h"

#include <QHostAddress>
#include <QSettings>
#include <QObject>
#include <QtTest>

class TestParaViewMCPServerConfig : public QObject
{
  Q_OBJECT

private slots:
  void initTestCase();
  void init();
  void loadsDefaults();
  void loadsPersistedSettings();
  void zeroPortFallsBackToDefault();
  void acceptsLoopbackWithoutToken();
  void rejectsNonLoopbackWithoutToken();
  void acceptsNonLoopbackWithToken();
  void rejectsInvalidHosts();
};

void TestParaViewMCPServerConfig::initTestCase()
{
  QCoreApplication::setOrganizationName(QStringLiteral("ParaViewMCPTests"));
  QCoreApplication::setApplicationName(QStringLiteral("ServerConfig"));
}

void TestParaViewMCPServerConfig::init()
{
  QSettings settings;
  settings.clear();
  settings.sync();
}

void TestParaViewMCPServerConfig::loadsDefaults()
{
  const ParaViewMCPServerConfig config = ParaViewMCPServerConfig::load();

  QCOMPARE(config.Host, QStringLiteral("127.0.0.1"));
  QCOMPARE(config.Port, ParaViewMCP::DefaultPort);
}

void TestParaViewMCPServerConfig::loadsPersistedSettings()
{
  ParaViewMCPServerConfig config;
  config.Host = QStringLiteral("localhost");
  config.Port = 12345;
  config.save();

  const ParaViewMCPServerConfig loaded = ParaViewMCPServerConfig::load();
  QCOMPARE(loaded.Host, QStringLiteral("localhost"));
  QCOMPARE(loaded.Port, static_cast<quint16>(12345));
}

void TestParaViewMCPServerConfig::zeroPortFallsBackToDefault()
{
  QSettings settings;
  settings.setValue(QStringLiteral("ParaViewMCP/ListenHost"), QStringLiteral("127.0.0.1"));
  settings.setValue(QStringLiteral("ParaViewMCP/ListenPort"), 0);

  const ParaViewMCPServerConfig loaded = ParaViewMCPServerConfig::load();
  QCOMPARE(loaded.Port, ParaViewMCP::DefaultPort);
}

void TestParaViewMCPServerConfig::acceptsLoopbackWithoutToken()
{
  ParaViewMCPServerConfig config;
  config.Host = QStringLiteral("localhost");
  config.AuthToken.clear();

  QHostAddress address;
  QString error;

  QVERIFY(config.validateForListen(&address, &error));
  QCOMPARE(address, QHostAddress(QHostAddress::LocalHost));
  QVERIFY(error.isEmpty());
}

void TestParaViewMCPServerConfig::rejectsNonLoopbackWithoutToken()
{
  ParaViewMCPServerConfig config;
  config.Host = QStringLiteral("0.0.0.0");
  config.AuthToken.clear();

  QString error;
  QVERIFY(!config.validateForListen(nullptr, &error));
  QCOMPARE(error, QStringLiteral("A non-loopback bind address requires an authentication token"));
}

void TestParaViewMCPServerConfig::acceptsNonLoopbackWithToken()
{
  ParaViewMCPServerConfig config;
  config.Host = QStringLiteral("0.0.0.0");
  config.AuthToken = QStringLiteral("secret");

  QHostAddress address;
  QVERIFY(config.validateForListen(&address, nullptr));
  QCOMPARE(address, QHostAddress(QStringLiteral("0.0.0.0")));
}

void TestParaViewMCPServerConfig::rejectsInvalidHosts()
{
  ParaViewMCPServerConfig config;
  config.Host = QStringLiteral("example.com");
  config.AuthToken = QStringLiteral("secret");

  QString error;
  QVERIFY(!config.validateForListen(nullptr, &error));
  QCOMPARE(error, QStringLiteral("Listen host must be 'localhost' or a literal IP address"));
}

QTEST_APPLESS_MAIN(TestParaViewMCPServerConfig)

#include "TestParaViewMCPServerConfig.moc"
