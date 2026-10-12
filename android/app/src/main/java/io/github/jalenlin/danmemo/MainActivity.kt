package io.github.jalenlin.danmemo

import android.Manifest
import android.annotation.SuppressLint
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.DocumentsContract
import android.provider.Settings
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import androidx.activity.ComponentActivity
import androidx.activity.addCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject
import java.io.File
import java.net.InetSocketAddress
import java.net.Socket
import kotlin.concurrent.thread

/**
 * One full-screen WebView. Python (tools/launcher.py, through android_main.py) serves the setup page and then
 * the player on 127.0.0.1; this activity unpacks tools/ and web/, asks for storage access (to read the user's
 * DanMemo folder), starts the server and points the WebView at it.
 */
class MainActivity : ComponentActivity() {
    private lateinit var root: FrameLayout
    private lateinit var web: WebView
    private var started = false
    private var asking = false
    private var fileCallback: ValueCallback<Array<Uri>>? = null
    private var customView: View? = null

    // <input type=file> on the setup page (choosing the APK)
    private val pickFile = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        fileCallback?.onReceiveValue(uri?.let { arrayOf(it) })
        fileCallback = null
    }
    // the setup page's "choose folder" (the backup): the system folder picker, turned into a file path for Python
    private val pickFolder = registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        val path = uri?.let { treePath(it) } ?: ""
        web.evaluateJavascript("window.__appFolder && window.__appFolder(${JSONObject.quote(path)})", null)
    }
    private val legacyPermission =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { asking = false; maybeStart() }

    private val userFolder get() = File(Environment.getExternalStorageDirectory(), "DanMemo")

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            window.attributes.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
        }
        if (applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE != 0) WebView.setWebContentsDebuggingEnabled(true)

        root = FrameLayout(this)
        web = WebView(this)
        root.addView(web, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        setContentView(root)
        web.setBackgroundColor(ContextCompat.getColor(this, R.color.bg))
        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true  // read marks and settings
            mediaPlaybackRequiresUserGesture = false  // voices and BGM start with the scene
            allowFileAccess = false
            userAgentString = "$userAgentString DanMemoApp"  // the player hides its full-screen button
        }
        web.addJavascriptInterface(Bridge(), "DanMemoApp")  // only our own pages load here (others open outside)
        web.webViewClient = object : WebViewClient() {
            // the player stays in the app; other links (GitHub, …) open in the browser
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val url = request.url
                if (url.host == "127.0.0.1") return false
                runCatching { startActivity(Intent(Intent.ACTION_VIEW, url)) }
                return true
            }
        }
        web.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(view: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams): Boolean {
                fileCallback?.onReceiveValue(null)
                fileCallback = callback
                runCatching { pickFile.launch("*/*") }.onFailure { fileCallback = null; callback.onReceiveValue(null) }
                return true
            }

            // element.requestFullscreen() (a video, the player)
            override fun onShowCustomView(view: View, callback: CustomViewCallback) {
                customView?.let { root.removeView(it) }
                customView = view
                root.addView(view, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
                web.visibility = View.GONE
            }

            override fun onHideCustomView() {
                customView?.let { root.removeView(it) }
                customView = null
                web.visibility = View.VISIBLE
            }
        }
        web.loadData("<body style='background:#0b1020;color:#9aa6c4;font-family:sans-serif;padding:24px'>" +
            getString(R.string.starting) + "</body>", "text/html; charset=utf-8", "utf-8")
        onBackPressedDispatcher.addCallback(this) {
            when {
                customView != null -> web.webChromeClient?.onHideCustomView()
                web.canGoBack() -> web.goBack()
                else -> finish()
            }
        }
    }

    override fun onResume() {
        super.onResume()
        hideSystemBars()
        maybeStart()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) hideSystemBars()
    }

    private fun hideSystemBars() {
        WindowInsetsControllerCompat(window, window.decorView).run {
            hide(WindowInsetsCompat.Type.systemBars())
            systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }
    }

    private fun hasStorage(): Boolean =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) Environment.isExternalStorageManager()
        else ContextCompat.checkSelfPermission(this, Manifest.permission.READ_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED

    private fun maybeStart() {
        if (started || asking) return
        if (hasStorage()) return start()
        asking = true
        AlertDialog.Builder(this)
            .setTitle(R.string.perm_title)
            .setMessage(getString(R.string.perm_body, userFolder.absolutePath))
            .setCancelable(false)
            .setPositiveButton(R.string.perm_ok) { _, _ ->
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                    asking = false  // checked again in onResume, when the user comes back
                    val app = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION, Uri.parse("package:$packageName"))
                    runCatching { startActivity(app) }.onFailure {
                        startActivity(Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION))
                    }
                } else {
                    legacyPermission.launch(arrayOf(Manifest.permission.READ_EXTERNAL_STORAGE,
                        Manifest.permission.WRITE_EXTERNAL_STORAGE))
                }
            }
            .setNegativeButton(R.string.perm_exit) { _, _ -> finish() }
            .show()
    }

    private fun start() {
        started = true
        userFolder.mkdirs()
        thread(name = "danmemo-start") {
            val app = unpack()
            if (!Python.isStarted()) Python.start(AndroidPlatform(this))
            val port = Python.getInstance().getModule("android_main")
                .callAttr("start", app.absolutePath, filesDir.absolutePath, userFolder.absolutePath).toInt()
            val deadline = System.currentTimeMillis() + 30_000
            while (System.currentTimeMillis() < deadline) {
                val up = runCatching { Socket().use { it.connect(InetSocketAddress("127.0.0.1", port), 200) } }.isSuccess
                if (up) break
                Thread.sleep(100)
            }
            runOnUiThread { web.loadUrl("http://127.0.0.1:$port/") }
        }
    }

    inner class Bridge {
        @JavascriptInterface
        fun pickFolder() = runOnUiThread { runCatching { pickFolder.launch(null) } }

        /** the player's "keep screen on" setting (while a story plays, always, or never) */
        @JavascriptInterface
        fun setKeepScreenOn(on: Boolean) = runOnUiThread {
            if (on) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    /** a folder from the system picker as a path: "primary:Download/dm" -> /storage/emulated/0/Download/dm,
     *  "1A2B-3C4D:dm" (an SD card) -> /storage/1A2B-3C4D/dm. Readable as a path with all-files access. */
    private fun treePath(uri: Uri): String? {
        if (uri.authority != "com.android.externalstorage.documents") return null
        val id = DocumentsContract.getTreeDocumentId(uri)
        val vol = id.substringBefore(":")
        val rel = id.substringAfter(":", "")
        val base = if (vol.equals("primary", ignoreCase = true)) Environment.getExternalStorageDirectory().path else "/storage/$vol"
        return if (rel.isEmpty()) base else "$base/$rel"
    }

    /** assets/app (tools/ and web/) -> files/app, again after each app update */
    private fun unpack(): File {
        val dst = File(filesDir, "app")
        val stamp = File(dst, ".installed")
        val version = packageManager.getPackageInfo(packageName, 0).lastUpdateTime.toString()
        if (stamp.exists() && stamp.readText() == version) return dst
        dst.deleteRecursively()
        fun copy(asset: String, to: File) {
            val children = assets.list(asset).orEmpty()
            if (children.isEmpty()) {
                to.parentFile?.mkdirs()
                assets.open(asset).use { input -> to.outputStream().use { input.copyTo(it) } }
            } else {
                to.mkdirs()
                for (c in children) copy("$asset/$c", File(to, c))
            }
        }
        copy("app", dst)
        stamp.writeText(version)
        return dst
    }
}
