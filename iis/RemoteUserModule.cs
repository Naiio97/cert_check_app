using System;
using System.Web;

// Modul IIS: po ověření uživatele (Windows Authentication) vloží jeho účet do hlavičky X-Remote-User,
// kterou pak ARR/URL Rewrite přepošle aplikaci. Pravidlo URL Rewrite s {LOGON_USER} to neumí, protože
// se vyhodnotí dřív, než je uživatel ověřen.
//
// Hlavičku nastavuje VŽDY (při neověřeném uživateli na prázdnou hodnotu), takže ji klient nemůže podvrhnout.
public class RemoteUserModule : IHttpModule
{
    private const string HeaderName = "X-Remote-User";

    public void Init(HttpApplication application)
    {
        application.PostAuthenticateRequest += OnPostAuthenticate;
    }

    private static void OnPostAuthenticate(object sender, EventArgs e)
    {
        HttpContext context = ((HttpApplication)sender).Context;
        string user = string.Empty;
        if (context.User != null && context.User.Identity != null && context.User.Identity.IsAuthenticated)
        {
            user = context.User.Identity.Name;
        }
        // Funguje jen v integrovaném režimu pipeline (ve starém "classic" režimu je Headers jen pro čtení).
        context.Request.Headers.Set(HeaderName, user);
    }

    public void Dispose()
    {
    }
}
