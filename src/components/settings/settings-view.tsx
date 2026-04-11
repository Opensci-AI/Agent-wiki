import { useChatStore } from "@/stores/chat-store"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import i18n from "@/i18n"
import { config } from "@/api/config"
import { toast } from "sonner"

const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "zh", label: "Chinese" },
  { value: "vi", label: "Tiếng Việt" },
]

const HISTORY_OPTIONS = [2, 4, 6, 8, 10, 20]

export function SettingsView() {
  const { t } = useTranslation()
  const maxHistoryMessages = useChatStore((s) => s.maxHistoryMessages)
  const setMaxHistoryMessages = useChatStore((s) => s.setMaxHistoryMessages)

  const [saving, setSaving] = useState(false)
  const [currentLang, setCurrentLang] = useState(i18n.language)

  async function handleSave() {
    setSaving(true)
    try {
      await config.update({ language: currentLang })
      toast.success(t("settings.saved") || "Settings saved")
    } catch (err) {
      console.error("Failed to save settings:", err)
      toast.error(t("settings.saveFailed") || "Failed to save settings")
    } finally {
      setSaving(false)
    }
  }

  async function handleLanguageChange(lang: string) {
    await i18n.changeLanguage(lang)
    setCurrentLang(lang)
  }

  return (
    <div className="h-full overflow-auto p-8">
      <div className="mx-auto max-w-xl">
        <h2 className="mb-6 text-2xl font-bold">{t("settings.title")}</h2>

        <div className="space-y-6">
          {/* Language section */}
          <div className="space-y-4 rounded-lg border p-4">
            <h3 className="font-semibold">{t("settings.language")}</h3>
            <div className="flex flex-wrap gap-2">
              {LANGUAGES.map((lang) => (
                <button
                  key={lang.value}
                  onClick={() => handleLanguageChange(lang.value)}
                  className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
                    currentLang === lang.value
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border hover:bg-accent"
                  }`}
                >
                  {lang.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">{t("settings.languageHint")}</p>
          </div>

          {/* LLM / Search config notice */}
          <div className="space-y-4 rounded-lg border p-4">
            <h3 className="font-semibold">LLM & Search Configuration</h3>
            <p className="text-sm text-muted-foreground">
              LLM provider, API keys, and search configuration are now managed by the backend server.
              Contact your administrator to update these settings.
            </p>
          </div>

          {/* Chat History section */}
          <div className="space-y-4 rounded-lg border p-4">
            <h3 className="font-semibold">Chat History</h3>
            <p className="text-xs text-muted-foreground">
              Number of previous messages included when talking to AI. More = better context but uses more tokens.
            </p>
            <div className="space-y-2">
              <Label>Max conversation messages sent to AI</Label>
              <div className="flex flex-wrap gap-2">
                {HISTORY_OPTIONS.map((n) => (
                  <button
                    key={n}
                    onClick={() => setMaxHistoryMessages(n)}
                    className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
                      maxHistoryMessages === n
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border hover:bg-accent"
                    }`}
                  >
                    {n}
                  </button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                Currently: {maxHistoryMessages} messages ({maxHistoryMessages / 2} rounds of conversation)
              </p>
            </div>
          </div>

          <Button onClick={handleSave} className="w-full" disabled={saving}>
            {saving ? t("settings.saving") || "Saving..." : t("settings.save")}
          </Button>
        </div>
      </div>
    </div>
  )
}
