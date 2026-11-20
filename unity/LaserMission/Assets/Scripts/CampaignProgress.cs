namespace LaserMission
{
    public sealed class CampaignProgress
    {
        public enum Phase { Playing, Retry, StageCleared, Complete }
        public const int LayoutCount = 4;
        readonly int[] layouts = new int[Room.MaxLevel];
        readonly System.Random random;

        public int Stage { get; private set; } = 1;
        public int LayoutSeed => layouts[Stage - 1];
        public Phase CurrentPhase { get; private set; } = Phase.Playing;

        public CampaignProgress(int? seed = null)
        {
            random = seed.HasValue ? new System.Random(seed.Value) : new System.Random();
            for (int i = 0; i < layouts.Length; i++)
                layouts[i] = seed.HasValue
                    ? (seed.Value % LayoutCount + LayoutCount) % LayoutCount
                    : random.Next(LayoutCount);
        }

        public void Finish(Room.Outcome outcome)
        {
            if (CurrentPhase != Phase.Playing || outcome == Room.Outcome.None) return;

            CurrentPhase = outcome != Room.Outcome.Goal ? Phase.Retry
                : Stage == Room.MaxLevel ? Phase.Complete : Phase.StageCleared;
        }

        public void Continue()
        {
            if (CurrentPhase == Phase.StageCleared) Stage++;
            else if (CurrentPhase == Phase.Complete)
            {
                Stage = 1;
                for (int i = 0; i < layouts.Length; i++) Reroll(i);
            }
            else Reroll(Stage - 1);
            CurrentPhase = Phase.Playing;
        }

        internal static int DrawLayout(System.Random random, int previous = -1) =>
            previous < 0 ? random.Next(LayoutCount)
                : (previous + random.Next(1, LayoutCount)) % LayoutCount;

        void Reroll(int index) => layouts[index] = DrawLayout(random, layouts[index]);
    }
}
