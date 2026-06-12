using UnrealBuildTool;

public class PorceTelemetry : ModuleRules
{
    public PorceTelemetry(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDefinitions.AddRange(
            new string[]
            {
                "NOMINMAX=1",
                "WIN32_LEAN_AND_MEAN=1"
            }
        );

        PublicDependencyModuleNames.AddRange(
            new string[]
            {
                "Core",
                "CoreUObject",
                "Engine",
                "HTTP",
                "Json",
                "JsonUtilities",
                "CesiumRuntime"
            }
        );
    }
}
