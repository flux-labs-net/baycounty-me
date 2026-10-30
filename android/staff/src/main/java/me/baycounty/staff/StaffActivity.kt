package me.baycounty.staff

import android.os.Bundle
import android.os.SystemClock
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_WEAK
import androidx.biometric.BiometricManager.Authenticators.DEVICE_CREDENTIAL
import androidx.biometric.BiometricPrompt
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity

/** BayCounty.me Staff. Locks behind the fingerprint, face or screen lock after 5 minutes away, because it can send
 *  alerts to every phone in a city. Extras for screenshots: demo=true, asStaff=true, asOfficial=true, screen=board|votes|overview|alerts|send|... */
class StaffActivity : FragmentActivity() {
    private lateinit var model: StaffModel
    private var locked by mutableStateOf(false)
    private var leftAt = 0L

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val demo = intent.getStringExtra("demo") == "true"
        model = if (demo) StaffModel(NoTokens, StaffModel.demoFrom(this), asStaff = intent.getStringExtra("asStaff") == "true",
                asOfficial = intent.getStringExtra("asOfficial") == "true")
                else StaffModel(PrefsTokenStore(this))
        locked = !demo && model.signedIn
        val screen = intent.getStringExtra("screen")
        setContent {
            StaffTheme(isSystemInDarkTheme()) {
                StaffApp(model, screen = screen, locked = locked, onUnlock = ::unlock)
            }
        }
    }

    override fun onStop() { super.onStop(); leftAt = SystemClock.elapsedRealtime() }

    override fun onStart() {
        super.onStart()
        if (model.demo == null && model.signedIn && leftAt > 0 && SystemClock.elapsedRealtime() - leftAt > 5 * 60_000) locked = true
        if (locked) unlock()
    }

    private fun unlock() {
        val kinds = BIOMETRIC_WEAK or DEVICE_CREDENTIAL
        if (BiometricManager.from(this).canAuthenticate(kinds) != BiometricManager.BIOMETRIC_SUCCESS) { locked = false; return }
        val prompt = BiometricPrompt(this, ContextCompat.getMainExecutor(this), object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) { locked = false; leftAt = 0 }
        })
        prompt.authenticate(BiometricPrompt.PromptInfo.Builder().setTitle("Unlock BayCounty.me Staff").setAllowedAuthenticators(kinds).build())
    }
}
