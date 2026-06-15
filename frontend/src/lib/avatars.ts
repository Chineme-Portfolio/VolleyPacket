// Preset avatars. Each `id` matches the backend's PRESET_AVATARS set and a bundled
// SVG at /avatars/{id}.svg (animals + alien from Twemoji; silhouettes are original).

export interface PresetAvatar {
  id: string;
  label: string;
  group: "Animals" | "Other" | "People";
}

export const PRESET_AVATARS: PresetAvatar[] = [
  { id: "koala", label: "Koala", group: "Animals" },
  { id: "panda", label: "Panda", group: "Animals" },
  { id: "bear", label: "Bear", group: "Animals" },
  { id: "kangaroo", label: "Kangaroo", group: "Animals" },
  { id: "dog", label: "Dog", group: "Animals" },
  { id: "cat", label: "Cat", group: "Animals" },
  { id: "mouse", label: "Mouse", group: "Animals" },
  { id: "alien", label: "Alien", group: "Other" },
  { id: "silhouette-male", label: "Male", group: "People" },
  { id: "silhouette-female", label: "Female", group: "People" },
  { id: "silhouette-nb", label: "Non-binary", group: "People" },
];

export const PRESET_IDS = new Set(PRESET_AVATARS.map((p) => p.id));

export const PRESET_GROUPS: PresetAvatar["group"][] = ["Animals", "Other", "People"];
