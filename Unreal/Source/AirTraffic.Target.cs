using UnrealBuildTool;
using System.Collections.Generic;

public class AirTrafficTarget : TargetRules
{
    public AirTrafficTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V5;
        ExtraModuleNames.AddRange(new string[] { "AirTraffic" });
    }
}
