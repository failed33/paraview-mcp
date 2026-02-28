#pragma once

#include <QDockWidget>

class QLabel;
class QLineEdit;
class QPlainTextEdit;
class QPushButton;
class QSpinBox;

class ParaViewMCPDockWindow : public QDockWidget
{
public:
  explicit ParaViewMCPDockWindow(QWidget* parent);

  void refreshFromController();

private:
  void syncState();

  QLineEdit* HostField = nullptr;
  QSpinBox* PortField = nullptr;
  QLineEdit* TokenField = nullptr;
  QLabel* StatusLabel = nullptr;
  QPlainTextEdit* LogOutput = nullptr;
  QPushButton* StartButton = nullptr;
  QPushButton* StopButton = nullptr;
};
