package cutctx

import "fmt"

// CutctxError represents an API error from the Cutctx proxy.
type CutctxError struct {
	Code   int    `json:"code"`
	Path   string `json:"path,omitempty"`
	Detail string `json:"detail,omitempty"`
}

func (e *CutctxError) Error() string {
	if e.Detail != "" {
		return fmt.Sprintf("cutctx: %s returned %d: %s", e.Path, e.Code, e.Detail)
	}
	return fmt.Sprintf("cutctx: %s returned status %d", e.Path, e.Code)
}
