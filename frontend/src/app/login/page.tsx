"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthStore } from "@/lib/auth";
import { ArrowRight, BarChart3, Inbox, Sparkles, Zap } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { login, register } = useAuthStore();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [teamName, setTeamName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (isRegister) {
        await register(email, password, name, teamName || undefined);
      } else {
        await login(email, password);
      }
      router.push("/dashboard");
    } catch (err: unknown) {
      const message =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setError(message || "操作失败，请重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-screen bg-background lg:grid-cols-[1.15fr_0.85fr]">
      <section className="hidden border-r bg-background p-10 lg:flex lg:flex-col">
        <div className="flex items-center gap-3">
          <div className="operator-brand-mark h-8 w-8">U</div>
          <div>
            <div className="operator-brand-name text-base">UGC Outreach</div>
            <div className="operator-brand-tag">Operator Workspace</div>
          </div>
        </div>

        <div className="flex flex-1 items-center">
          <div className="max-w-xl">
            <div className="operator-eyebrow mb-3">Brand ops command center</div>
            <h1 className="text-4xl font-bold leading-tight tracking-tight">
              把达人发现、建联活动和 AI 回复审核放进同一个工作台。
            </h1>
            <p className="mt-5 max-w-lg text-sm leading-7 text-muted-foreground">
              新版界面采用 warm paper / ink / amber 的 operator workspace 风格，
              更适合日常扫描、批量处理和团队协作。
            </p>
            <div className="mt-8 grid max-w-lg gap-3">
              {[
                { icon: Sparkles, label: "发现达人", detail: "从 Woto 数据源筛选可触达创作者" },
                { icon: BarChart3, label: "数据看板", detail: "集中查看触达、打开、回复和退信表现" },
                { icon: Inbox, label: "AI 回复台", detail: "低风险草稿审核后快速发送" },
              ].map((item) => {
                const Icon = item.icon;
                return (
                  <div key={item.label} className="operator-card flex items-center gap-3 p-4">
                    <div className="grid h-9 w-9 place-items-center rounded-md bg-muted">
                      <Icon className="h-4 w-4 text-foreground" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold">{item.label}</div>
                      <div className="text-xs text-muted-foreground">{item.detail}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      <main className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-3">
              <div className="operator-brand-mark">U</div>
              <div>
                <div className="operator-brand-name">UGC Outreach</div>
                <div className="operator-brand-tag">Operator Workspace</div>
              </div>
            </div>
          </div>

          <div className="operator-card p-6">
            <div className="mb-6">
              <div className="mb-3 inline-flex items-center gap-2 rounded-full border bg-muted px-2.5 py-1 text-xs font-semibold text-muted-foreground">
                <Zap className="h-3.5 w-3.5 text-brand" />
                {isRegister ? "Create workspace" : "Welcome back"}
              </div>
              <h1 className="text-2xl font-bold tracking-tight">
                {isRegister ? "创建新账户" : "登录工作台"}
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                {isRegister ? "创建团队并开始配置建联系统。" : "继续处理达人发现、活动和回复。"}
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
          {isRegister && (
            <>
              <div>
                <Label htmlFor="name">姓名</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
              <div>
                <Label htmlFor="teamName">团队名称</Label>
                <Input
                  id="teamName"
                  value={teamName}
                  onChange={(e) => setTeamName(e.target.value)}
                  placeholder="可选"
                />
              </div>
            </>
          )}

          <div>
            <Label htmlFor="email">邮箱</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <Label htmlFor="password">密码</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {error && <p className="text-sm text-red-500">{error}</p>}

              <button
                type="submit"
                className="inline-flex h-9 w-full items-center justify-center gap-2 rounded-md bg-foreground px-3 text-sm font-semibold text-background transition-colors hover:bg-foreground/90 disabled:opacity-60"
                disabled={loading}
              >
                {loading ? "处理中..." : isRegister ? "注册" : "登录"}
                {!loading && <ArrowRight className="h-4 w-4" />}
              </button>
            </form>

            <div className="mt-4 text-center">
              <button
                type="button"
                onClick={() => {
                  setIsRegister(!isRegister);
                  setError("");
                }}
                className="text-sm font-medium text-foreground underline-offset-4 hover:underline"
              >
                {isRegister ? "已有账户？去登录" : "没有账户？去注册"}
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
