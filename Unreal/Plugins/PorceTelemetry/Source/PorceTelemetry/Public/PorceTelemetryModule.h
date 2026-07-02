#pragma once

#include "Containers/Ticker.h"
#include "Modules/ModuleManager.h"

class FPorceTelemetryModule final : public IModuleInterface
{
public:
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;

private:
    FTSTicker::FDelegateHandle BenchmarkTickerHandle;
    bool bBenchmarkRunnerSpawned = false;

    bool HandleBenchmarkTicker(float DeltaTime);
};
