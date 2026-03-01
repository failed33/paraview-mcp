#pragma once

#include <QToolBar>

class ParaViewMCPPopup;
class QToolButton;

class ParaViewMCPToolbar : public QToolBar
{
  Q_OBJECT

public:
  ParaViewMCPToolbar(const QString& title, QWidget* parent = nullptr);
  ParaViewMCPToolbar(QWidget* parent = nullptr);
  ~ParaViewMCPToolbar() override;

private:
  void constructor();
  void updateButtonAppearance();

  QToolButton* Button = nullptr;
  ParaViewMCPPopup* Popup = nullptr;
};
