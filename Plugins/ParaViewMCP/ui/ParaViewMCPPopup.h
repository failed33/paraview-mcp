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
